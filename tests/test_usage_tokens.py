"""Tests for token-accurate usage parsing and cost estimation."""

from __future__ import annotations

import json
import re
from datetime import date, datetime, timezone
from pathlib import Path

from typer.testing import CliRunner

from grok_build_cli_utilities.cli import app
from grok_build_cli_utilities.utils.auth_status import format_weekly_reset_local
from grok_build_cli_utilities.utils.pricing import (
    DEFAULT_CASH_SCALE,
    DEFAULT_CASH_SCALE_API,
    DEFAULT_CASH_SCALE_SUPERGROK_OVERAGE,
    DEFAULT_CASH_SCALE_SUPERGROK_POOL,
    DEFAULT_HEAVY_USD,
    DEFAULT_HEAVY_WEEKLY_INCLUDE_USD,
    DEFAULT_SUPERGROK_USD,
    api_estimate_usd,
    effective_rates,
    plan_advisor,
    rates_for_model,
    resolve_cash_scale,
)
from grok_build_cli_utilities.utils.usage_tokens import (
    PaygoTypeUsd,
    UsageRec,
    aggregate,
    allocate_invoice,
    allocate_paygo,
    allocate_paygo_by_type,
    bucket_key,
    filter_usage,
    load_turn_usage,
    pr_group_key,
    pr_labels_from_update,
    resolve_usage_date_tz,
    scan_pr_creates,
    total_bucket,
)

runner = CliRunner()


def _plain_cli(text: str) -> str:
    """Strip ANSI and collapse wrap so help assertions do not depend on COLUMNS."""
    stripped = re.sub(r"\x1b\[[0-9;]*[A-Za-z]", "", text or "")
    return " ".join(stripped.split())


def _json_from_cli(result) -> dict:
    """Parse JSON from CLI result; ignore stderr warnings mixed into output."""
    text = result.stdout or result.output or ""
    start = text.find("{")
    assert start >= 0, f"no JSON in output: {text[:200]!r}"
    return json.loads(text[start:])


def _write_turn(
    path: Path,
    *,
    prompt_id: str,
    ts: str,
    input_t: int,
    output_t: int,
    cached: int,
    reasoning: int,
    ticks: int,
    model: str = "grok-build-0.1",
    total: int | None = None,
) -> None:
    tot = total if total is not None else input_t + output_t
    usage = {
        "inputTokens": input_t,
        "outputTokens": output_t,
        "totalTokens": tot,
        "cachedReadTokens": cached,
        "reasoningTokens": reasoning,
        "costUsdTicks": ticks,
        "modelCalls": 1,
        "modelUsage": {
            model: {
                "inputTokens": input_t,
                "outputTokens": output_t,
                "totalTokens": tot,
                "cachedReadTokens": cached,
                "reasoningTokens": reasoning,
                "costUsdTicks": ticks,
                "modelCalls": 1,
            }
        },
    }
    obj = {
        "method": "session/update",
        "timestamp": ts,
        "params": {
            "sessionId": path.parent.name,
            "update": {
                "sessionUpdate": "turn_completed",
                "prompt_id": prompt_id,
                "usage": usage,
            },
        },
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(obj) + "\n")


def _append_update(path: Path, obj: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(obj) + "\n")


def _mcp_create_pr_update(
    *,
    session_id: str,
    number: int,
    owner: str = "example",
    repo: str = "widgets",
    body: str = "",
    ts: str = "2026-08-02T12:05:00Z",
) -> dict:
    html = f"https://github.com/{owner}/{repo}/pull/{number}"
    ok = {
        "url": f"https://api.github.com/repos/{owner}/{repo}/pulls/{number}",
        "html_url": html,
        "number": number,
        "title": f"pr {number}",
        "body": body,
        "user": {"html_url": f"https://github.com/{owner}"},
    }
    return {
        "method": "session/update",
        "timestamp": ts,
        "params": {
            "sessionId": session_id,
            "update": {
                "sessionUpdate": "tool_call_update",
                "toolCallId": f"call-create-{number}",
                "status": "completed",
                "rawOutput": {
                    "type": "MCP",
                    "tool_name": "create_pull_request",
                    "server_name": "github",
                    "output": {"OkayOutput": json.dumps(ok)},
                },
            },
        },
    }


def _mcp_get_pr_update(*, session_id: str, number: int) -> dict:
    html = f"https://github.com/example/widgets/pull/{number}"
    ok = {"html_url": html, "number": number, "title": f"dependabot {number}"}
    return {
        "method": "session/update",
        "timestamp": "2026-08-02T12:06:00Z",
        "params": {
            "sessionId": session_id,
            "update": {
                "sessionUpdate": "tool_call_update",
                "toolCallId": f"call-get-{number}",
                "status": "completed",
                "title": "github__get_pull_request",
                "rawOutput": {
                    "type": "MCP",
                    "tool_name": "get_pull_request",
                    "server_name": "github",
                    "output": {"OkayOutput": json.dumps(ok)},
                },
            },
        },
    }


def test_list_price_usd_matches_xai_ticks():
    from grok_build_cli_utilities.utils.usage_tokens import (
        TICKS_PER_USD,
        list_price_usd,
        turn_list_usd,
    )
    from grok_build_cli_utilities.utils.usage_tokens import UsageRec
    from datetime import datetime, timezone

    assert TICKS_PER_USD == 10_000_000_000
    # update-for-46 /usage Cost $1.5465
    assert abs(list_price_usd(15_464_980_000) - 1.546498) < 1e-9
    # widgets /usage Cost $77.3463 (mid-session snapshot)
    assert abs(list_price_usd(773_463_000_000) - 77.3463) < 1e-9
    rec = UsageRec(
        prompt_id="t",
        ts=datetime(2026, 8, 13, tzinfo=timezone.utc),
        project="P",
        cwd="/P",
        session_id="s",
        input=1_000_000,
        cached=1_000_000,
        total=1_000_000,
        ticks=15_464_980_000,
    )
    assert abs(turn_list_usd(rec) - 1.546498) < 1e-9
    # -m / prefer_ticks=False reconstructs 4.6 cached $0.50
    assert abs(turn_list_usd(rec, rates_for_model("grok-4.6"), prefer_ticks=False) - 0.50) < 1e-9


def test_api_estimate_math():
    # 1M cached @ 0.20 + 1M uncached @ 1.00 + 0.5M out @ 2.00 = 0.2+1+1 = 2.2
    est = api_estimate_usd(
        cached=1_000_000,
        uncached_in=1_000_000,
        output=500_000,
        reasoning=0,
        rates=rates_for_model("grok-build"),
    )
    assert abs(est - 2.2) < 1e-9


def test_rates_for_model_fuzzy():
    from grok_build_cli_utilities.utils.pricing import (
        DEFAULT_RATES_MODEL,
        resolve_rates_model,
    )

    r = rates_for_model("grok-4.5-build")
    # Matches console grok-4.5 Pricing (≤200k): input $2 / cached $0.30 / output $6
    assert r.cached_input == 0.30
    assert r.uncached_input == 2.00
    assert r.output == 6.00
    r46 = rates_for_model("grok-4.6")
    # docs.x.ai 2026-08-13: $2 / $0.50 / $6 (cached is the 4.5→4.6 list-rate delta)
    assert r46.label == "grok-4.6"
    assert r46.cached_input == 0.50
    assert r46.uncached_input == 2.00
    assert r46.output == 6.00
    r2 = rates_for_model("unknown-xyz")
    assert r2.uncached_input == 2.00  # default is grok-4.6-class
    assert r2.cached_input == 0.50
    assert DEFAULT_RATES_MODEL == "grok-4.6"
    r3 = rates_for_model("grok-build-0.1")
    assert r3.cached_input == 0.20
    label, rates = resolve_rates_model("4.5")
    assert label == "grok-4.5"
    assert rates.output == 6.00
    label46, rates46 = resolve_rates_model("4.6")
    assert label46 == "grok-4.6"
    assert rates46.cached_input == 0.50
    _label2, rates2 = resolve_rates_model("build")
    assert rates2.cached_input == 0.20
    # grok-4 must not steal grok-4.6* (old substring match billed $3/$15)
    for alias in ("grok-4.6", "4.6", "grok-4.6-build", "grok-4.6-fast"):
        got = rates_for_model(alias)
        assert got.label == "grok-4.6", alias
        assert got.cached_input == 0.50, alias
        assert got.output == 6.00, alias
    assert rates_for_model("grok-4").output == 15.00
    assert rates_for_model("grok-4-0709").output == 15.00


def test_load_dedupe_and_filter(tmp_path: Path):
    # encoded cwd style path
    sess = tmp_path / "sessions" / "%2FUsers%2Fme%2FDocuments%2FGitHub%2Fnotes" / "sid1"
    upd = sess / "updates.jsonl"
    _write_turn(
        upd,
        prompt_id="p1",
        ts="2026-08-02T12:00:00Z",
        input_t=1_000_000,
        output_t=1000,
        cached=900_000,
        reasoning=100,
        ticks=1_000_000_000,
    )
    # lower total same prompt — should be ignored
    _write_turn(
        upd,
        prompt_id="p1",
        ts="2026-08-02T12:01:00Z",
        input_t=100,
        output_t=1,
        cached=0,
        reasoning=0,
        ticks=1,
        total=50,
    )
    # out of range
    _write_turn(
        upd,
        prompt_id="p2",
        ts="2026-07-01T12:00:00Z",
        input_t=10,
        output_t=1,
        cached=0,
        reasoning=0,
        ticks=1,
    )
    # second prompt in range
    _write_turn(
        upd,
        prompt_id="p3",
        ts="2026-08-03T12:00:00Z",
        input_t=500_000,
        output_t=500,
        cached=400_000,
        reasoning=50,
        ticks=500_000_000,
    )

    recs = load_turn_usage(tmp_path / "sessions")
    assert len(recs) == 3  # p1 kept max, p2, p3
    filtered = filter_usage(
        recs, date_from=date(2026, 8, 1), date_to=date(2026, 8, 5), tz=timezone.utc
    )
    assert len(filtered) == 2
    assert all(r.project == "notes" for r in filtered)

    buckets = aggregate(filtered, "app")
    assert len(buckets) == 1
    b = buckets[0]
    assert b.n == 2
    assert b.cached == 1_300_000
    tot = total_bucket(filtered)
    assert tot.api_est() > 0


def test_invoice_allocation(tmp_path: Path):
    sess = tmp_path / "sessions" / "projA" / "s1"
    upd = sess / "updates.jsonl"
    _write_turn(
        upd,
        prompt_id="a",
        ts="2026-08-01T00:00:00Z",
        input_t=1000,
        output_t=10,
        cached=0,
        reasoning=0,
        ticks=100,
    )
    sess2 = tmp_path / "sessions" / "projB" / "s2"
    upd2 = sess2 / "updates.jsonl"
    _write_turn(
        upd2,
        prompt_id="b",
        ts="2026-08-01T01:00:00Z",
        input_t=1000,
        output_t=10,
        cached=0,
        reasoning=0,
        ticks=300,
    )
    recs = load_turn_usage(tmp_path / "sessions")
    buckets = aggregate(recs, "app")
    scale, fixed_per = allocate_invoice(
        buckets,
        invoice_usd=40.0,
        fixed_usd=8.0,
        group="app",
    )
    # scale = 40/400 = 0.1
    assert abs(scale - 0.1) < 1e-9
    assert abs(fixed_per - 4.0) < 1e-9  # 8/2 buckets
    by_key = {b.key: b for b in buckets}
    # proj names from path
    vars_ = {k: b.ticks * scale for k, b in by_key.items()}
    assert abs(sum(vars_.values()) - 40.0) < 1e-6


def test_usage_cost_cli_json(tmp_path: Path):
    grok = tmp_path / ".grok"
    sess = grok / "sessions" / "%2Ftmp%2FMyApp" / "s1"
    upd = sess / "updates.jsonl"
    _write_turn(
        upd,
        prompt_id="p1",
        ts="2026-08-02T12:00:00Z",
        input_t=1_000_000,
        output_t=2000,
        cached=800_000,
        reasoning=500,
        ticks=2_000_000_000,
        model="grok-build-0.1",
    )
    # summary so other commands still work if needed
    (sess / "summary.json").write_text(
        json.dumps(
            {
                "info": {"id": "s1", "cwd": "/tmp/MyApp"},
                "created_at": "2026-08-02T12:00:00Z",
                "num_messages": 2,
                "current_model_id": "grok-build-0.1",
            }
        )
    )

    r = runner.invoke(
        app,
        [
            "-g",
            str(grok),
            "usage",
            "cost",
            "--from",
            "2026-08-01",
            "--to",
            "2026-08-05",
            "--by",
            "app",
            "--invoice-usd",
            "10",
            "--fixed-usd",
            "2",
            "--json",
        ],
    )
    assert r.exit_code == 0, r.output
    data = _json_from_cli(r)
    assert data["mode"] == "tokens"
    assert data["totals"]["prompts"] == 1
    assert data["totals"]["list_usd"] > 0 or data["totals"].get("api_est_usd", 0) > 0
    assert data["invoice"]["invoice_usd"] == 10
    assert data["totals"]["est_usd"] >= 0


def test_usage_cost_rough_compat(tmp_path: Path):
    grok = tmp_path / ".grok"
    sess = grok / "sessions" / "p" / "s1"
    sess.mkdir(parents=True)
    (sess / "summary.json").write_text(
        json.dumps(
            {
                "info": {"id": "s1", "cwd": "/p"},
                "created_at": "2026-06-01T00:00:00Z",
                "num_messages": 10,
                "current_model_id": "grok-3",
            }
        )
    )
    r = runner.invoke(
        app, ["-g", str(grok), "usage", "cost", "--mode", "rough", "--by", "model", "--json"]
    )
    assert r.exit_code == 0
    assert "rough" in r.output
    assert "estimated_total_usd" in r.output


def test_usage_report_tokens(tmp_path: Path):
    grok = tmp_path / ".grok"
    sess = grok / "sessions" / "AppX" / "s1"
    upd = sess / "updates.jsonl"
    _write_turn(
        upd,
        prompt_id="p1",
        ts="2026-08-02T12:00:00Z",
        input_t=100_000,
        output_t=100,
        cached=50_000,
        reasoning=10,
        ticks=1000,
    )
    r = runner.invoke(app, ["-g", str(grok), "usage", "report", "--by", "app", "--json"])
    assert r.exit_code == 0, r.output
    data = _json_from_cli(r)
    assert data["mode"] == "tokens"
    assert data["totals"]["prompts"] == 1
    # Redundant --tokens with --by app should warn but still succeed
    r2 = runner.invoke(
        app, ["-g", str(grok), "usage", "report", "--tokens", "--by", "app", "--json"]
    )
    assert r2.exit_code == 0, r2.output
    assert "ignored" in (r2.output + r2.stderr).lower()


def test_usage_info():
    r = runner.invoke(app, ["usage", "info"])
    assert r.exit_code == 0
    assert "SuperGrok" in r.output


def test_usage_info_and_cost_help_mention_cwd_and_native_pr_create():
    info = runner.invoke(app, ["usage", "info"])
    assert info.exit_code == 0, info.output
    blob = info.output
    assert "cwd" in blob
    assert "inferred from cwd" in blob
    assert "create_pull_request" in blob
    assert "gh pr create" in blob
    assert "get_pull_request" in blob
    help_r = runner.invoke(app, ["usage", "cost", "--help"])
    assert help_r.exit_code == 0, help_r.output
    h = help_r.output
    assert "cwd" in h
    assert "inferred from cwd" in h
    assert "create_pull_request" in h
    assert "gh pr create" in h


def test_allocate_paygo_sums_to_total(tmp_path: Path):
    sess = tmp_path / "sessions" / "A" / "s1"
    upd = sess / "updates.jsonl"
    _write_turn(
        upd,
        prompt_id="a",
        ts="2026-08-01T00:00:00Z",
        input_t=1000,
        output_t=10,
        cached=0,
        reasoning=0,
        ticks=100,
    )
    sess2 = tmp_path / "sessions" / "B" / "s2"
    _write_turn(
        sess2 / "updates.jsonl",
        prompt_id="b",
        ts="2026-08-01T01:00:00Z",
        input_t=1000,
        output_t=10,
        cached=0,
        reasoning=0,
        ticks=300,
    )
    recs = load_turn_usage(tmp_path / "sessions")
    buckets = aggregate(recs, "app")
    alloc = allocate_paygo(buckets, paygo_usd=5.43, weight="ticks")
    assert abs(sum(alloc.values()) - 5.43) < 1e-9
    # 100:300 → 25%:75%
    assert abs(max(alloc.values()) - 5.43 * 0.75) < 1e-6


def test_usage_cost_est_cash_scale_json(tmp_path: Path):
    grok = tmp_path / ".grok"
    sess = grok / "sessions" / "AppY" / "s1"
    _write_turn(
        sess / "updates.jsonl",
        prompt_id="p1",
        ts="2026-08-02T12:00:00Z",
        input_t=1_000_000,
        output_t=1000,
        cached=500_000,
        reasoning=100,
        ticks=1_000_000_000,
    )
    r = runner.invoke(
        app,
        [
            "-g",
            str(grok),
            "usage",
            "cost",
            "--from",
            "2026-08-01",
            "--to",
            "2026-08-04",
            "--by",
            "app",
            "--rates-model",
            "grok-4.5",
            "--cash-scale",
            "0.48",
            "--json",
        ],
    )
    assert r.exit_code == 0, r.output
    data = _json_from_cli(r)
    assert data["rates_model"] == "grok-4.5"
    assert data["cash_scale"] == 0.48
    assert data["rates"]["cached_input"] == 0.3
    list_t = data["totals"]["list_usd"]
    est_t = data["totals"]["est_usd"]
    assert abs(est_t - list_t * 0.48) < 1e-3
    # effective = list × scale
    assert abs(data["effective_rates"]["uncached_input"] - 2.0 * 0.48) < 1e-6
    assert abs(data["effective_rates"]["cached_input"] - 0.3 * 0.48) < 1e-6
    assert abs(data["effective_rates"]["output"] - 6.0 * 0.48) < 1e-6


def test_effective_rates_uniform_scale():
    r = rates_for_model("grok-4.5")
    eff = effective_rates(r, 0.5656)
    assert abs(eff.uncached_input - 2.0 * 0.5656) < 1e-9
    assert abs(eff.cached_input - 0.3 * 0.5656) < 1e-9
    assert abs(eff.output - 6.0 * 0.5656) < 1e-9
    assert DEFAULT_CASH_SCALE == DEFAULT_CASH_SCALE_API == 1.0
    assert DEFAULT_CASH_SCALE_SUPERGROK_POOL == 0.0
    assert DEFAULT_CASH_SCALE_SUPERGROK_OVERAGE == 1.9


def test_resolve_cash_scale_by_auth_path():
    s, src = resolve_cash_scale(auth_effective="api_key")
    assert s == 1.0
    assert "api_key" in src
    s, src = resolve_cash_scale(auth_effective="supergrok_session", weekly_usage_pct=10.0)
    assert s == 0.0
    assert "pool" in src
    s, src = resolve_cash_scale(auth_effective="supergrok_session", weekly_usage_pct=100.0)
    assert s == 1.9
    assert "overage" in src
    s, src = resolve_cash_scale(auth_effective="supergrok_session", weekly_usage_pct=None)
    assert s == 1.0
    assert "unknown" in src


def test_build_token_cost_window_est_by_key(tmp_path: Path):
    """Shared builder: one-pass est_by_key matches totals; regimes split."""
    from datetime import datetime, timezone

    from grok_build_cli_utilities.utils.auth_status import AuthHistoryEvent
    from grok_build_cli_utilities.utils.pricing import estimate_with_auth_mix, rates_for_model
    from grok_build_cli_utilities.utils.usage_cost_window import build_token_cost_window
    from grok_build_cli_utilities.utils.usage_tokens import UsageRec, load_turn_usage

    grok = tmp_path / ".grok"
    sess = grok / "sessions" / "AppX" / "s1"
    sess.mkdir(parents=True)
    (grok / "auth.json").write_text('{"access_token": "' + "x" * 40 + '"}', encoding="utf-8")
    _write_turn(
        sess / "updates.jsonl",
        prompt_id="p1",
        ts="2026-08-07T12:00:00Z",
        input_t=1_000_000,
        output_t=0,
        cached=1_000_000,
        reasoning=0,
        ticks=1,
        total=1_000_000,
    )
    records = load_turn_usage(grok / "sessions")
    win = build_token_cost_window(grok, records, group="app", rates_model="grok-4.5")
    assert win.list_total > 0
    assert win.est_by_key
    assert abs(sum(win.est_by_key.values()) - win.est_total) < 1e-6

    # Regime split: pool + overage as separate paths
    rates = rates_for_model("grok-4.5")
    r_pool = UsageRec(
        prompt_id="pool",
        ts=datetime(2026, 8, 7, 12, 0, tzinfo=timezone.utc),
        project="A",
        cwd="/A",
        session_id="s",
        input=1_000_000,
        cached=1_000_000,
        total=1_000_000,
    )
    r_ov = UsageRec(
        prompt_id="ov",
        ts=datetime(2026, 8, 6, 12, 0, tzinfo=timezone.utc),
        project="A",
        cwd="/A",
        session_id="s",
        input=1_000_000,
        cached=1_000_000,
        total=1_000_000,
    )
    pts = [AuthHistoryEvent("2026-08-01T00:00:00+00:00", "cached_token", "sel")]
    weekly_tl = [
        (datetime(2026, 8, 6, 11, 0, tzinfo=timezone.utc), 100.0),
        (datetime(2026, 8, 7, 11, 0, tzinfo=timezone.utc), 10.0),
    ]
    mix = estimate_with_auth_mix(
        [r_pool, r_ov],
        rates,
        change_points=pts,
        weekly_timeline=weekly_tl,
        fallback_auth="supergrok_session",
        group_key_fn=lambda r: r.project,
    )
    paths = {s.path for s in mix.slices}
    assert "supergrok_pool" in paths
    assert "supergrok_overage" in paths
    assert abs(mix.est_by_key["A"] - mix.est_total) < 1e-6


def test_apply_topoff_discount_25_and_100():
    from grok_build_cli_utilities.utils.pricing import (
        apply_topoff_discount,
        ceil_to_pack_usd,
        resolve_topoff_discount,
        resolve_topoff_discount_scenarios,
        topoff_discount_label,
    )
    from grok_build_cli_utilities.utils.usage_display import _reconcile_pcts

    assert abs(apply_topoff_discount(100.0, 0.25) - 75.0) < 1e-9
    assert abs(apply_topoff_discount(100.0, 1.0) - 0.0) < 1e-9
    assert abs(apply_topoff_discount(100.0, 1.5) - 0.0) < 1e-9  # clamp to 1.0
    d, src = resolve_topoff_discount(cli_discount=1.0)
    assert d == 1.0
    assert "1" in src
    d, src = resolve_topoff_discount({"topoff_discount": 0.25})
    assert abs(d - 0.25) < 1e-9
    scenarios = resolve_topoff_discount_scenarios(None)
    assert scenarios == [0.20, 0.25, 0.40]
    assert 0.0 not in scenarios and 1.0 not in scenarios
    scenarios = resolve_topoff_discount_scenarios(
        {"topoff_discount_scenarios": [0.0, 0.4]}, active_discount=0.25
    )
    # 0.0 dropped (full price is base row); 0.4 + active 0.25 kept
    assert 0.0 not in scenarios and 0.4 in scenarios and 0.25 in scenarios
    assert "40" in topoff_discount_label(0.40) or "promo" in topoff_discount_label(0.40)
    # Pack rounding: $380 face → $400 @ $100 packs
    assert abs(ceil_to_pack_usd(380.0, 100.0) - 400.0) < 1e-9
    assert abs(ceil_to_pack_usd(100.0, 100.0) - 100.0) < 1e-9
    assert abs(ceil_to_pack_usd(0.0, 100.0) - 0.0) < 1e-9
    # Regime % always sum to 100
    assert sum(_reconcile_pcts([93.4, 5.2, 1.4])) == 100
    assert sum(_reconcile_pcts([1.0, 1.0, 1.0])) == 100


def test_estimate_with_auth_mix_splits_paths():
    from datetime import datetime, timezone

    from grok_build_cli_utilities.utils.auth_status import AuthHistoryEvent
    from grok_build_cli_utilities.utils.pricing import estimate_with_auth_mix
    from grok_build_cli_utilities.utils.usage_tokens import UsageRec

    rates = rates_for_model("grok-4.5")
    # 1M cached only → list$ 0.30 each
    r_sg = UsageRec(
        prompt_id="a",
        ts=datetime(2026, 8, 6, 12, 0, tzinfo=timezone.utc),
        project="A",
        cwd="/A",
        session_id="s1",
        input=1_000_000,
        cached=1_000_000,
        total=1_000_000,
    )
    r_api = UsageRec(
        prompt_id="b",
        ts=datetime(2026, 8, 7, 16, 0, tzinfo=timezone.utc),
        project="A",
        cwd="/A",
        session_id="s1",
        input=1_000_000,
        cached=1_000_000,
        total=1_000_000,
    )
    pts = [
        AuthHistoryEvent("2026-08-06T10:00:00+00:00", "cached_token", "sel"),
        AuthHistoryEvent("2026-08-07T15:00:00+00:00", "xai.api_key", "sel"),
    ]
    # Per-turn weekly timeline: SuperGrok hour at 100% overage, not current 10%
    weekly_tl = [
        (datetime(2026, 8, 6, 11, 0, tzinfo=timezone.utc), 100.0),
        (datetime(2026, 8, 7, 14, 0, tzinfo=timezone.utc), 10.0),
    ]
    mix = estimate_with_auth_mix(
        [r_sg, r_api],
        rates,
        change_points=pts,
        weekly_usage_pct=10.0,  # "current" — must NOT zero historical SuperGrok
        weekly_timeline=weekly_tl,
        fallback_auth="supergrok_session",
    )
    assert mix.source == "auth_mix"
    by_path = {s.path: s for s in mix.slices}
    # SuperGrok at 100% weekly → overage slice (regime-split path)
    assert "supergrok_overage" in by_path
    assert "api_key" in by_path
    assert abs(by_path["supergrok_overage"].est_usd - 0.30 * 1.9) < 1e-6
    assert abs(by_path["api_key"].est_usd - 0.30) < 1e-6
    assert abs(mix.est_total - (0.30 * 1.9 + 0.30)) < 1e-6


def test_historical_supergrok_without_weekly_uses_list_unknown():
    """Before an *overage* first sample, SuperGrok must not invent pool 0 or 1.9."""
    from datetime import datetime, timezone

    from grok_build_cli_utilities.utils.auth_status import AuthHistoryEvent
    from grok_build_cli_utilities.utils.pricing import estimate_with_auth_mix
    from grok_build_cli_utilities.utils.usage_tokens import UsageRec

    rates = rates_for_model("grok-4.5")
    r = UsageRec(
        prompt_id="old",
        ts=datetime(2026, 8, 3, 12, 0, tzinfo=timezone.utc),
        project="A",
        cwd="/A",
        session_id="s1",
        input=1_000_000,
        cached=1_000_000,
        total=1_000_000,
    )
    pts = [AuthHistoryEvent("2026-08-01T00:00:00+00:00", "cached_token", "sel")]
    # weekly timeline only starts Aug 6; Aug 3 has no sample → unknown@list 1.0
    weekly_tl = [(datetime(2026, 8, 6, 12, 0, tzinfo=timezone.utc), 100.0)]
    mix = estimate_with_auth_mix(
        [r],
        rates,
        change_points=pts,
        weekly_usage_pct=8.0,
        weekly_timeline=weekly_tl,
        fallback_auth="supergrok_session",
    )
    assert abs(mix.est_total - 0.30 * 1.0) < 1e-6
    assert mix.slices and mix.slices[0].path == "supergrok_unknown"


def test_pre_log_in_pool_heavy_uses_pool_not_list():
    """Truncated billing log: first sample still in-pool → earlier same-week Heavy is pool 0."""
    from datetime import datetime, timezone

    from grok_build_cli_utilities.utils.auth_status import AuthHistoryEvent
    from grok_build_cli_utilities.utils.pricing import estimate_with_auth_mix
    from grok_build_cli_utilities.utils.usage_tokens import UsageRec

    rates = rates_for_model("grok-4.5")
    r = UsageRec(
        prompt_id="old",
        ts=datetime(2026, 8, 20, 2, 0, tzinfo=timezone.utc),
        project="widgets",
        cwd="/widgets",
        session_id="s1",
        input=1_000_000,
        cached=1_000_000,
        total=1_000_000,
    )
    pts = [AuthHistoryEvent("2026-08-01T00:00:00+00:00", "cached_token", "sel")]
    weekly_tl = [(datetime(2026, 8, 22, 12, 0, tzinfo=timezone.utc), 15.0)]
    tier_tl = [(datetime(2026, 8, 22, 12, 0, tzinfo=timezone.utc), "heavy")]
    mix = estimate_with_auth_mix(
        [r],
        rates,
        change_points=pts,
        weekly_usage_pct=45.0,
        weekly_timeline=weekly_tl,
        tier_timeline=tier_tl,
        fallback_auth="supergrok_session",
    )
    assert mix.slices and mix.slices[0].path == "heavy_pool"
    assert mix.est_total == 0.0


def test_auth_mix_labels_heavy_pool_from_tier_timeline():
    from datetime import datetime, timezone

    from grok_build_cli_utilities.utils.auth_status import AuthHistoryEvent
    from grok_build_cli_utilities.utils.pricing import estimate_with_auth_mix
    from grok_build_cli_utilities.utils.usage_tokens import UsageRec

    rates = rates_for_model("grok-4.5")
    r = UsageRec(
        prompt_id="hv",
        ts=datetime(2026, 8, 16, 15, 0, tzinfo=timezone.utc),
        project="A",
        cwd="/A",
        session_id="s1",
        input=1_000_000,
        cached=1_000_000,
        total=1_000_000,
    )
    pts = [AuthHistoryEvent("2026-08-01T00:00:00+00:00", "cached_token", "sel")]
    weekly_tl = [(datetime(2026, 8, 16, 12, 0, tzinfo=timezone.utc), 10.0)]
    tier_tl = [
        (datetime(2026, 8, 16, 11, 0, tzinfo=timezone.utc), "supergrok"),
        (datetime(2026, 8, 16, 13, 12, tzinfo=timezone.utc), "heavy"),
    ]
    mix = estimate_with_auth_mix(
        [r],
        rates,
        change_points=pts,
        weekly_usage_pct=10.0,
        weekly_timeline=weekly_tl,
        tier_timeline=tier_tl,
        fallback_auth="supergrok_session",
    )
    assert mix.slices and mix.slices[0].path == "heavy_pool"
    assert mix.est_total == 0.0


def test_plan_advisor_high_volume_prefers_heavy():
    # ~20d window, ~$358 list, scale 0.57 → est ~$204 (user sample intensity)
    a = plan_advisor(
        list_usd=357.64,
        est_usd=203.85,
        tokens=865_700_000,
        cache_pct=95.3,
        cash_scale=0.57,
        window_days=20,
        project_days=30,
    )
    assert a.api_list_monthly > 500
    assert 300 < a.api_est_monthly < 330
    # SuperGrok: small weekly include → large list overage
    assert a.supergrok.overage_list_usd > 100
    assert a.supergrok.monthly > DEFAULT_SUPERGROK_USD + 100
    # Heavy: large include → flat ~$300
    assert a.heavy.overage_list_usd < 1.0
    assert abs(a.heavy.monthly - DEFAULT_HEAVY_USD) < 1.0
    assert a.winner == "heavy"
    assert a.heavy_cheaper_than_list_api is True
    assert a.heavy_breakeven_tokens_monthly is not None
    assert a.heavy_breakeven_tokens_monthly > 0


def test_plan_advisor_low_volume_api_est_wins():
    a = plan_advisor(
        list_usd=20.0,
        est_usd=11.4,
        tokens=5_000_000,
        cache_pct=90.0,
        cash_scale=0.57,
        window_days=30,
        project_days=30,
    )
    assert a.api_list_monthly == 20.0
    assert a.supergrok.overage_list_usd == 0.0
    assert a.winner == "api_est"
    assert DEFAULT_HEAVY_WEEKLY_INCLUDE_USD == 150.0


def test_plan_advisor_export_mirrors_tui_promos_and_active_pin():
    """--json candidates match -P: Heavy promo rows when tops exist, active pin."""
    from grok_build_cli_utilities.utils.usage_display import plan_advisor_export

    # 2d window at ~$45.32 list$ → ~$680/mo (PR Heavy sample). Advisor Pure API
    # uses API-scale list$, not mixed est$. SuperGrok pack tops ~$600; Heavy still
    # has a pack so hv_* rows exist and ★ is Heavy @ −40% (not SuperGrok @ −40%).
    a = plan_advisor(
        list_usd=45.32,
        est_usd=45.32,
        tokens=279_700_000,
        cache_pct=98.0,
        cash_scale=1.0,
        window_days=2,
        project_days=30,
    )
    assert a.heavy.overage_list_usd > 0.5
    assert a.supergrok.overage_list_usd > 100

    out = plan_advisor_export(a, active_topoff_discount=0.25)
    by_id = {c["id"]: c for c in out["candidates"]}
    assert {
        "api",
        "sg_full",
        "hv_full",
        "sg_20",
        "sg_25",
        "sg_40",
        "hv_20",
        "hv_25",
        "hv_40",
    } <= set(by_id)
    for cid, c in by_id.items():
        assert "active" in c
        if cid in ("sg_25", "hv_25"):
            assert c["active"] is True
        else:
            assert c["active"] is False
    assert by_id["hv_full"]["pack_tops_face"] > 0.5
    assert out["best"]["id"] == "hv_40"

    low = plan_advisor(
        list_usd=20.0,
        est_usd=11.4,
        tokens=5_000_000,
        cache_pct=90.0,
        cash_scale=0.57,
        window_days=30,
        project_days=30,
    )
    low_out = plan_advisor_export(low, active_topoff_discount=0.0)
    low_ids = {c["id"] for c in low_out["candidates"]}
    assert "hv_full" in low_ids
    assert "hv_40" not in low_ids
    assert all(c["active"] is False for c in low_out["candidates"])


def test_usage_report_by_app_includes_est(tmp_path: Path):
    """Token report --by app shows list$ + est$ with cash_scale."""
    grok = tmp_path / ".grok"
    sess = grok / "sessions" / "AppR" / "s1"
    _write_turn(
        sess / "updates.jsonl",
        prompt_id="p1",
        ts="2026-08-02T12:00:00Z",
        input_t=1_000_000,
        output_t=0,
        cached=1_000_000,
        reasoning=0,
        ticks=1,
        total=1_000_000,
    )
    # list$ = 1M cached * 0.30 = 0.30; est at 0.5 = 0.15
    r = runner.invoke(
        app,
        [
            "-g",
            str(grok),
            "usage",
            "report",
            "--by",
            "app",
            "--from",
            "2026-08-01",
            "--to",
            "2026-08-04",
            "-m",
            "grok-4.5",
            "--cash-scale",
            "0.5",
            "--json",
        ],
    )
    assert r.exit_code == 0, r.output
    data = _json_from_cli(r)
    assert data["mode"] == "tokens"
    assert data["cash_scale"] == 0.5
    assert abs(data["totals"]["list_usd"] - 0.30) < 1e-6
    assert abs(data["totals"]["est_usd"] - 0.15) < 1e-6
    assert abs(data["buckets"][0]["est_usd"] - 0.15) < 1e-6
    assert data["result_from"] == "2026-08-02"
    assert data["result_to"] == "2026-08-02"


def test_usage_cost_plan_advisor_json(tmp_path: Path):
    grok = tmp_path / ".grok"
    sess = grok / "sessions" / "AppPA" / "s1"
    # Two days of usage so window_days >= 2
    _write_turn(
        sess / "updates.jsonl",
        prompt_id="p1",
        ts="2026-08-01T12:00:00Z",
        input_t=10_000_000,
        output_t=1000,
        cached=9_000_000,
        reasoning=100,
        ticks=1,
    )
    _write_turn(
        sess / "updates.jsonl",
        prompt_id="p2",
        ts="2026-08-10T12:00:00Z",
        input_t=10_000_000,
        output_t=1000,
        cached=9_000_000,
        reasoning=100,
        ticks=1,
    )
    r = runner.invoke(
        app,
        [
            "-g",
            str(grok),
            "usage",
            "cost",
            "--from",
            "2026-08-01",
            "--to",
            "2026-08-10",
            "-m",
            "grok-4.5",
            "--plan-advisor",
            "--json",
        ],
    )
    assert r.exit_code == 0, r.output
    data = _json_from_cli(r)
    pa = data["plan_advisor"]
    assert pa is not None
    assert pa["window_days"] == 10
    assert pa["project_days"] == 30
    assert "candidates" in pa and "best" in pa
    ids = {c["id"] for c in pa["candidates"]}
    assert "api" in ids and "sg_full" in ids and "hv_full" in ids
    assert pa["best"]["id"] in ids
    assert data.get("wallet") is not None
    assert sum(s.get("list_pct") or 0 for s in data["auth_mix"]["slices"]) == 100


def test_usage_cost_detects_heavy_from_billing_log(tmp_path: Path):
    grok = tmp_path / ".grok"
    grok.mkdir()
    sess = grok / "sessions" / "AppH" / "s1"
    (grok / "auth.json").write_text(
        json.dumps({"access_token": "x" * 40, "email": "u@example.com"}),
        encoding="utf-8",
    )
    log_dir = grok / "logs"
    log_dir.mkdir(parents=True)
    (log_dir / "unified.jsonl").write_text(
        json.dumps(
            {
                "ts": "2026-08-16T13:12:24Z",
                "msg": "billing: fetched credits config",
                "ctx": {
                    "subscriptionTier": "SuperGrok Heavy",
                    "config": {
                        "creditUsagePercent": 16.0,
                        "prepaidBalance": {"val": 15208},
                        "currentPeriod": {
                            "type": "USAGE_PERIOD_TYPE_WEEKLY",
                            "start": "2026-08-13T23:08:01+00:00",
                            "end": "2026-08-20T23:08:01+00:00",
                        },
                    },
                },
            }
        )
        + "\n",
        encoding="utf-8",
    )
    _write_turn(
        sess / "updates.jsonl",
        prompt_id="p1",
        ts="2026-08-16T15:00:00Z",
        input_t=1_000_000,
        output_t=0,
        cached=1_000_000,
        reasoning=0,
        ticks=10_000_000_000,
        total=1_000_000,
    )
    r = runner.invoke(
        app,
        [
            "-g",
            str(grok),
            "usage",
            "cost",
            "--from",
            "2026-08-16",
            "--to",
            "2026-08-16",
            "-P",
            "--json",
        ],
    )
    assert r.exit_code == 0, r.output
    data = _json_from_cli(r)
    assert data["wallet"]["subscription_tier"] == "heavy"
    assert data["wallet"]["subscription_tier_label"] == "Heavy"
    assert data["wallet"]["weekly_resets_at"] is not None
    assert data["wallet"]["weekly_resets_at"].startswith("2026-08-20T23:08:01")
    assert data["plan_advisor"]["current_tier"] == "heavy"
    paths = {s["path"] for s in data["auth_mix"]["slices"]}
    assert "heavy_pool" in paths

    human = runner.invoke(
        app,
        [
            "-g",
            str(grok),
            "usage",
            "cost",
            "--from",
            "2026-08-16",
            "--to",
            "2026-08-16",
            "-P",
        ],
    )
    assert human.exit_code == 0, human.output
    out = human.output
    assert "Heavy pool" in out or "auth Heavy session" in out
    assert "current plan" in out
    assert "what-if" in out
    assert "Plan from billing log: SuperGrok Heavy" in out
    reset = format_weekly_reset_local(datetime(2026, 8, 20, 23, 8, 1, tzinfo=timezone.utc))
    assert reset is not None
    reset_lines = [
        ln for ln in out.splitlines() if reset in ln and "Weekly Heavy pool resets" in ln
    ]
    assert reset_lines, out
    assert all("Extra Credits" not in ln for ln in reset_lines)


def test_usage_cost_from_before_data_warns(tmp_path: Path):
    """--from earlier than any session turn → warning with actual earliest date."""
    grok = tmp_path / ".grok"
    sess = grok / "sessions" / "AppEarly" / "s1"
    _write_turn(
        sess / "updates.jsonl",
        prompt_id="p1",
        ts="2026-08-03T12:00:00Z",
        input_t=1000,
        output_t=10,
        cached=0,
        reasoning=0,
        ticks=1,
    )
    r = runner.invoke(
        app,
        [
            "-g",
            str(grok),
            "usage",
            "cost",
            "--from",
            "2026-07-01",
            "--by",
            "app",
            "-m",
            "grok-4.5",
            "--json",
        ],
    )
    assert r.exit_code == 0, r.output
    # Warning on stderr; JSON on stdout
    combined = (r.stdout or "") + (r.stderr or "") + (r.output or "")
    assert "before earliest session data" in combined
    assert "2026-08-03" in combined
    data = _json_from_cli(r)
    assert data["from"] == "2026-07-01"
    assert data["data_earliest"] == "2026-08-03"
    assert data["result_from"] == "2026-08-03"


def test_usage_cost_prepaid_sets_scale(tmp_path: Path):
    grok = tmp_path / ".grok"
    sess = grok / "sessions" / "AppY" / "s1"
    _write_turn(
        sess / "updates.jsonl",
        prompt_id="p1",
        ts="2026-08-02T12:00:00Z",
        input_t=1_000_000,
        output_t=0,
        cached=1_000_000,
        reasoning=0,
        ticks=1,
        total=1_000_000,
    )
    # list$ at 4.5 = 1M cached * 0.30 = 0.30; burn=0.15 → scale=0.5
    r = runner.invoke(
        app,
        [
            "-g",
            str(grok),
            "usage",
            "cost",
            "--from",
            "2026-08-01",
            "--to",
            "2026-08-04",
            "-m",
            "grok-4.5",
            "--prepaid-usd",
            "1.0",
            "--credits-remaining",
            "0.85",
            "--json",
        ],
    )
    assert r.exit_code == 0, r.output
    data = _json_from_cli(r)
    assert abs(data["cash_scale"] - 0.5) < 1e-6
    assert abs(data["totals"]["est_usd"] - 0.15) < 1e-6
    assert abs(data["effective_rates"]["cached_input"] - 0.15) < 1e-6  # 0.30 × 0.5


def test_allocate_paygo_by_type():
    # Two apps: A is cache-heavy, B is uncached-heavy
    from grok_build_cli_utilities.utils.usage_tokens import UsageBucket

    a = UsageBucket(key="A", n=1, input=900, cached=800, output=10, reasoning=0, total=910)
    b = UsageBucket(key="B", n=1, input=200, cached=50, output=90, reasoning=10, total=300)
    types = PaygoTypeUsd(cached=3.28, input=1.76, output=0.25, reasoning=0.05)
    bill, detail = allocate_paygo_by_type([a, b], types)
    assert abs(sum(bill.values()) - types.total) < 1e-6
    # A has most cache → most of cached $
    assert detail["A"]["cached_usd"] > detail["B"]["cached_usd"]
    # B has more completion → more of output $
    assert detail["B"]["output_usd"] > detail["A"]["output_usd"]


def test_usage_cost_rates_model_switch(tmp_path: Path):
    grok = tmp_path / ".grok"
    sess = grok / "sessions" / "AppZ" / "s1"
    _write_turn(
        sess / "updates.jsonl",
        prompt_id="p1",
        ts="2026-08-02T12:00:00Z",
        input_t=1_000_000,
        output_t=0,
        cached=1_000_000,
        reasoning=0,
        ticks=0,
        total=1_000_000,
    )
    base = ["-g", str(grok), "usage", "cost", "--from", "2026-08-01", "--to", "2026-08-04"]
    r45 = runner.invoke(app, [*base, "-m", "grok-4.5", "--json"])
    r46 = runner.invoke(app, [*base, "-m", "grok-4.6", "--json"])
    r_default = runner.invoke(app, [*base, "--json"])
    r_build = runner.invoke(app, [*base, "-m", "grok-build-0.1", "--json"])
    assert r45.exit_code == 0 and r46.exit_code == 0
    assert r_default.exit_code == 0 and r_build.exit_code == 0
    d45 = _json_from_cli(r45)
    d46 = _json_from_cli(r46)
    ddef = _json_from_cli(r_default)
    db = _json_from_cli(r_build)
    # 1M cached, no ticks: 4.5 → $0.30; 4.6 / default fallback → $0.50; build → $0.20
    assert abs(d45["totals"]["list_usd"] - 0.30) < 1e-6
    assert abs(d46["totals"]["list_usd"] - 0.50) < 1e-6
    assert d46["rates_model"] == "grok-4.6"
    assert ddef["list_source"] == "rates"
    assert abs(ddef["totals"]["list_usd"] - 0.50) < 1e-6
    assert abs(db["totals"]["list_usd"] - 0.20) < 1e-6


def test_usage_cost_default_uses_ticks(tmp_path: Path):
    grok = tmp_path / ".grok"
    sess = grok / "sessions" / "AppT" / "s1"
    _write_turn(
        sess / "updates.jsonl",
        prompt_id="p1",
        ts="2026-08-13T12:00:00Z",
        input_t=1_000_000,
        output_t=0,
        cached=1_000_000,
        reasoning=0,
        ticks=15_464_980_000,  # /usage $1.546498
        total=1_000_000,
    )
    r = runner.invoke(
        app,
        ["-g", str(grok), "usage", "cost", "--from", "2026-08-13", "--json"],
    )
    assert r.exit_code == 0, r.output
    data = _json_from_cli(r)
    assert data["list_source"] == "ticks"
    assert abs(data["totals"]["list_usd"] - 1.5465) < 1e-4
    # -m still reconstructs and ignores ticks
    r_m = runner.invoke(
        app,
        ["-g", str(grok), "usage", "cost", "--from", "2026-08-13", "-m", "grok-4.6", "--json"],
    )
    d_m = _json_from_cli(r_m)
    assert d_m["list_source"] == "rates"
    assert abs(d_m["totals"]["list_usd"] - 0.50) < 1e-6


def test_scan_pr_creates_mcp_and_ignores_get_and_prose(tmp_path: Path):
    sess = tmp_path / "sessions" / "App" / "s1"
    upd = sess / "updates.jsonl"
    _write_turn(
        upd,
        prompt_id="p1",
        ts="2026-08-02T12:00:00Z",
        input_t=100,
        output_t=10,
        cached=0,
        reasoning=0,
        ticks=1000,
    )
    _append_update(
        upd,
        _mcp_create_pr_update(
            session_id="s1",
            number=85,
            body="mentions https://github.com/example/widgets/pull/70 in the body",
        ),
    )
    _append_update(upd, _mcp_get_pr_update(session_id="s1", number=58))
    _append_update(
        upd,
        {
            "method": "session/update",
            "timestamp": "2026-08-02T12:07:00Z",
            "params": {
                "sessionId": "s1",
                "update": {
                    "sessionUpdate": "agent_message_chunk",
                    "content": {
                        "type": "text",
                        "text": "Dependabot #58 https://github.com/example/widgets/pull/58",
                    },
                },
            },
        },
    )
    labels = scan_pr_creates(upd)
    assert labels == {"widgets#85"}
    assert "58" not in "".join(labels)
    assert "70" not in "".join(labels)


def test_pr_labels_from_string_raw_output():
    ok = json.dumps(
        {
            "number": 85,
            "html_url": "https://github.com/example/widgets/pull/85",
        }
    )
    blob = json.dumps({"tool_name": "create_pull_request", "OkayOutput": ok})
    labels = pr_labels_from_update(
        {
            "sessionUpdate": "tool_call_update",
            "status": "completed",
            "rawOutput": blob,
        }
    )
    assert labels == ["widgets#85"]


def test_pr_labels_from_gh_pr_create_stdout_not_pull_new():
    labels = pr_labels_from_update(
        {
            "sessionUpdate": "tool_call_update",
            "status": "completed",
            "rawOutput": {
                "type": "Bash",
                "command": "gh pr create --title x --body 'see #58 and pull/70'",
                "exit_code": 0,
                "output_for_prompt": (
                    "remote:      https://github.com/example/widgets/pull/new/feat-x\n"
                    "https://github.com/example/widgets/pull/91\n"
                ),
            },
        }
    )
    assert labels == ["widgets#91"]


def test_usage_cost_by_session_without_pr_tools(tmp_path: Path):
    grok = tmp_path / ".grok"
    sess = grok / "sessions" / "AppS" / "sessA"
    _write_turn(
        sess / "updates.jsonl",
        prompt_id="p1",
        ts="2026-08-02T12:00:00Z",
        input_t=100,
        output_t=10,
        cached=0,
        reasoning=0,
        ticks=2_000_000_000,
    )
    r = runner.invoke(
        app,
        [
            "-g",
            str(grok),
            "usage",
            "cost",
            "--from",
            "2026-08-01",
            "--to",
            "2026-08-05",
            "--by",
            "session",
            "--json",
        ],
    )
    assert r.exit_code == 0, r.output
    data = _json_from_cli(r)
    assert data["by"] == "session"
    assert data["buckets"][0]["key"] == "sessA"
    assert "prs" not in data["buckets"][0]
    r_pr = runner.invoke(
        app,
        [
            "-g",
            str(grok),
            "usage",
            "cost",
            "--from",
            "2026-08-01",
            "--to",
            "2026-08-05",
            "--by",
            "pr",
            "--json",
        ],
    )
    assert r_pr.exit_code == 0, r_pr.output
    assert "No created PRs" in (r_pr.output + r_pr.stderr)


def test_usage_cost_by_session_and_pr_one_to_one(tmp_path: Path):
    grok = tmp_path / ".grok"
    sess = grok / "sessions" / "widgets" / "s1"
    upd = sess / "updates.jsonl"
    _write_turn(
        upd,
        prompt_id="p1",
        ts="2026-08-02T12:00:00Z",
        input_t=100,
        output_t=10,
        cached=0,
        reasoning=0,
        ticks=5_000_000_000,
    )
    _append_update(upd, _mcp_create_pr_update(session_id="s1", number=85))
    args = [
        "-g",
        str(grok),
        "usage",
        "cost",
        "--from",
        "2026-08-01",
        "--to",
        "2026-08-05",
        "--json",
    ]
    by_sess = _json_from_cli(runner.invoke(app, [*args, "--by", "session"]))
    by_pr = _json_from_cli(runner.invoke(app, [*args, "--by", "pr"]))
    assert by_sess["buckets"][0]["key"] == "s1"
    assert by_sess["buckets"][0]["prs"] == ["widgets#85"]
    assert by_pr["buckets"][0]["key"] == "widgets#85"
    assert by_pr["buckets"][0]["prs"] == ["widgets#85"]
    assert abs(by_pr["totals"]["list_usd"] - by_sess["totals"]["list_usd"]) < 1e-9
    assert len(by_pr["buckets"]) == 1


def test_usage_cost_by_pr_does_not_split_multi(tmp_path: Path):
    grok = tmp_path / ".grok"
    sid = "01a059cb-5e07-7893-aab3-bad45b49c8ab"
    sess = grok / "sessions" / "widgets" / sid
    upd = sess / "updates.jsonl"
    _write_turn(
        upd,
        prompt_id="p1",
        ts="2026-08-02T12:00:00Z",
        input_t=100,
        output_t=10,
        cached=0,
        reasoning=0,
        ticks=8_000_000_000,
    )
    _append_update(
        upd,
        _mcp_create_pr_update(
            session_id=sid,
            number=70,
            body="later also https://github.com/example/widgets/pull/58",
        ),
    )
    _append_update(upd, _mcp_create_pr_update(session_id=sid, number=72, ts="2026-08-02T13:00:00Z"))
    args = [
        "-g",
        str(grok),
        "usage",
        "cost",
        "--from",
        "2026-08-01",
        "--to",
        "2026-08-05",
        "--json",
    ]
    by_sess = _json_from_cli(runner.invoke(app, [*args, "--by", "session"]))
    by_pr = _json_from_cli(runner.invoke(app, [*args, "--by", "pr"]))
    assert len(by_sess["buckets"]) == 1
    assert by_sess["buckets"][0]["prs"] == [
        "widgets#70",
        "widgets#72",
    ]
    expect = pr_group_key(sid, by_sess["buckets"][0]["prs"])
    assert expect == "widgets #70,72"
    assert "01a059cb" not in expect
    assert len(by_pr["buckets"]) == 1
    assert by_pr["buckets"][0]["key"] == expect
    assert abs(by_pr["totals"]["list_usd"] - by_sess["totals"]["list_usd"]) < 1e-9
    assert abs(by_pr["buckets"][0]["list_usd"] - by_sess["buckets"][0]["list_usd"]) < 1e-9


def test_usage_cost_by_pr_include_unlabeled(tmp_path: Path):
    grok = tmp_path / ".grok"
    labeled = grok / "sessions" / "AppL" / "lab"
    bare = grok / "sessions" / "AppU" / "unlab"
    _write_turn(
        labeled / "updates.jsonl",
        prompt_id="a",
        ts="2026-08-02T12:00:00Z",
        input_t=100,
        output_t=1,
        cached=0,
        reasoning=0,
        ticks=1000,
    )
    _append_update(
        labeled / "updates.jsonl",
        _mcp_create_pr_update(session_id="lab", number=3, repo="VCI", owner="example"),
    )
    _write_turn(
        bare / "updates.jsonl",
        prompt_id="b",
        ts="2026-08-02T13:00:00Z",
        input_t=100,
        output_t=1,
        cached=0,
        reasoning=0,
        ticks=2000,
    )
    r = runner.invoke(
        app,
        [
            "-g",
            str(grok),
            "usage",
            "cost",
            "--from",
            "2026-08-01",
            "--to",
            "2026-08-05",
            "--by",
            "pr",
            "--include-unlabeled",
            "--json",
        ],
    )
    assert r.exit_code == 0, r.output
    data = _json_from_cli(r)
    keys = {b["key"] for b in data["buckets"]}
    assert "VCI#3" in keys
    assert "unlab" in keys


def test_session_display_key_has_no_uuid_when_labeled():
    from grok_build_cli_utilities.utils.usage_tokens import (
        CreatedPr,
        session_display_key,
    )

    one = CreatedPr("example", "widgets", pr=83, issue=81)
    shown = session_display_key("01a059cb-deadbeef", [one], project="widgets")
    assert shown == "widgets#81→#83"
    assert "01a0" not in shown
    bare = session_display_key("01a059cb-deadbeef", [], project="widgets")
    assert bare == "widgets"


def test_pr_group_key_prefers_issue_and_drops_uuid():
    from grok_build_cli_utilities.utils.usage_tokens import CreatedPr, pr_group_key

    one = CreatedPr("example", "widgets", pr=83, issue=81)
    assert pr_group_key("01a059cb-dead", [one]) == "widgets#81→#83"
    same_repo = [
        CreatedPr("example", "widgets", pr=70, issue=69),
        CreatedPr("example", "widgets", pr=72, issue=71),
    ]
    assert pr_group_key("01a059cb-dead", same_repo) == "widgets #69,71"
    assert pr_group_key("01a059cb-dead", list(reversed(same_repo))) == "widgets #69,71"
    mixed = [
        CreatedPr("example", "widgets", pr=80, issue=7),
        CreatedPr("example", "widgets", pr=81, issue=8),
        CreatedPr("example", "widgets", pr=82, issue=14),
        CreatedPr("example", "notes", pr=15, issue=None),
    ]
    assert pr_group_key("01a05e3c-dead", mixed) == "widgets #7,8,14 · notes #15"


def test_pr_group_key_sorts_mixed_repos_by_number():
    from grok_build_cli_utilities.utils.usage_tokens import (
        CreatedPr,
        pr_group_key,
        sorted_pr_labels,
    )

    mixed = [
        CreatedPr("example", "notes", pr=15, issue=None),
        CreatedPr("example", "widgets", pr=80, issue=7),
        CreatedPr("example", "widgets", pr=81, issue=8),
        CreatedPr("example", "widgets", pr=82, issue=14),
    ]
    expect = "widgets #7,8,14 · notes #15"
    assert pr_group_key("01a05e3c-dead", mixed) == expect
    assert pr_group_key("01a05e3c-dead", list(reversed(mixed))) == expect
    assert sorted_pr_labels(mixed) == [
        "widgets#7",
        "widgets#8",
        "widgets#14",
        "notes#15",
    ]


def test_usage_cost_by_session_table_sorts_mixed_repo_numbers(tmp_path: Path):
    grok = tmp_path / ".grok"
    sess = grok / "sessions" / "mixed" / "mix"
    upd = sess / "updates.jsonl"
    _write_turn(
        upd,
        prompt_id="p1",
        ts="2026-08-02T12:00:00Z",
        input_t=100,
        output_t=10,
        cached=0,
        reasoning=0,
        ticks=5_000_000_000,
    )
    _append_update(
        upd,
        _mcp_create_pr_update(
            session_id="mix",
            number=15,
            owner="example",
            repo="notes",
        ),
    )
    _append_update(
        upd,
        _mcp_create_pr_update(
            session_id="mix",
            number=80,
            repo="widgets",
            body="Fixes #7",
        ),
    )
    _append_update(
        upd,
        _mcp_create_pr_update(
            session_id="mix",
            number=81,
            repo="widgets",
            body="Fixes #8",
        ),
    )
    _append_update(
        upd,
        _mcp_create_pr_update(
            session_id="mix",
            number=82,
            repo="widgets",
            body="Fixes #14",
        ),
    )
    r = runner.invoke(
        app,
        [
            "-g",
            str(grok),
            "usage",
            "cost",
            "--from",
            "2026-08-01",
            "--to",
            "2026-08-05",
            "--by",
            "session",
        ],
    )
    assert r.exit_code == 0, r.output
    blob = r.output + (r.stdout or "")
    compact = " ".join(blob.split())
    assert "widgets #7,8,14" in compact
    assert "widgets#14" not in compact
    by_pr = _json_from_cli(
        runner.invoke(
            app,
            [
                "-g",
                str(grok),
                "usage",
                "cost",
                "--from",
                "2026-08-01",
                "--to",
                "2026-08-05",
                "--by",
                "pr",
                "--json",
            ],
        )
    )
    assert by_pr["buckets"][0]["key"] == "widgets #7,8,14 · notes #15"


def test_usage_cost_by_session_keeps_duplicate_display_keys(tmp_path: Path):
    grok = tmp_path / ".grok"
    for sid, ticks in (("sid-a", 5_000_000_000), ("sid-b", 1_000_000_000)):
        sess = grok / "sessions" / "widgets-issue-69" / sid
        _write_turn(
            sess / "updates.jsonl",
            prompt_id=sid,
            ts="2026-08-02T12:00:00Z",
            input_t=100,
            output_t=1,
            cached=0,
            reasoning=0,
            ticks=ticks,
        )
    args = [
        "-g",
        str(grok),
        "usage",
        "cost",
        "--from",
        "2026-08-01",
        "--to",
        "2026-08-05",
        "--by",
        "session",
    ]
    data = _json_from_cli(runner.invoke(app, [*args, "--json"]))
    assert [b["key"] for b in data["buckets"]] == ["sid-a", "sid-b"]
    r = runner.invoke(app, args)
    assert r.exit_code == 0, r.output
    blob = r.output + (r.stdout or "")
    assert "widgets#69 · sid-a" in blob
    assert "widgets#69 · sid-b" in blob
    assert "widgets-issue-69" not in blob


def test_usage_cost_by_pr_uses_fixes_issue(tmp_path: Path):
    grok = tmp_path / ".grok"
    sess = grok / "sessions" / "widgets" / "s1"
    upd = sess / "updates.jsonl"
    _write_turn(
        upd,
        prompt_id="p1",
        ts="2026-08-02T12:00:00Z",
        input_t=100,
        output_t=10,
        cached=0,
        reasoning=0,
        ticks=1000,
    )
    _append_update(
        upd,
        _mcp_create_pr_update(
            session_id="s1",
            number=83,
            body="Fixes #81\n\nAlso mentions https://github.com/example/widgets/pull/58",
        ),
    )
    _append_update(upd, _mcp_get_pr_update(session_id="s1", number=58))
    r = runner.invoke(
        app,
        [
            "-g",
            str(grok),
            "usage",
            "cost",
            "--from",
            "2026-08-01",
            "--to",
            "2026-08-05",
            "--by",
            "pr",
            "--json",
        ],
    )
    assert r.exit_code == 0, r.output
    data = _json_from_cli(r)
    assert data["buckets"][0]["key"] == "widgets#81→#83"
    assert data["buckets"][0]["prs"] == ["widgets#81"]
    blob = json.dumps(data)
    assert "#58" not in blob
    assert "01a0" not in data["buckets"][0]["key"]


def test_pretty_app_name_worktree_and_issue_clone():
    from grok_build_cli_utilities.utils.usage_tokens import pretty_app_name

    wt = (
        "/Users/me/.grok/worktrees/github-grok-build-cli-utilities/"
        "subagent-01a05ed6-818e-7c70-9f5f-8acfd1e861a1"
    )
    assert pretty_app_name("subagent-01a05ed6-818e-7c70-9f5f-8acfd1e861a1", wt) == (
        "grok-build-cli-utilities (worktree)"
    )
    labeled = "/Users/me/.grok/worktrees/github-grok-build-cli-utilities/update-for-46"
    assert pretty_app_name("update-for-46", labeled) == ("grok-build-cli-utilities (update-for-46)")
    assert (
        pretty_app_name(
            "notes-issue-9",
            "/Users/me/Documents/GitHub/notes-issue-9",
        )
        == "notes#9"
    )
    assert pretty_app_name("notes", "/Users/me/Documents/GitHub/notes") == "notes"


def test_app_repo_name_github_issue_and_worktree():
    from grok_build_cli_utilities.utils.usage_tokens import app_repo_name

    assert app_repo_name("/Users/me/Documents/GitHub/widgets") == "widgets"
    assert app_repo_name("/Users/me/Documents/GitHub/widgets-issue-9") == "widgets"
    assert app_repo_name("/Users/me/src/widgets-issue-9") == "widgets"
    assert (
        app_repo_name(
            "/Users/me/.grok/worktrees/github-widgets/subagent-01a05ed6-818e-7c70-9f5f-8acfd1e861a1"
        )
        == "widgets"
    )
    assert (
        app_repo_name("/Users/me/.grok/worktrees/github-alice-Widgets/Widgets-issue-9") == "Widgets"
    )
    assert (
        app_repo_name(
            "/Users/me/.grok/worktrees/github-alice-Widgets/"
            "subagent-01a05ed6-818e-7c70-9f5f-8acfd1e861a1"
        )
        == "Widgets"
    )
    assert (
        app_repo_name(
            "/Users/me/.grok/worktrees/github-notes-cli/subagent-01a05ed6-818e-7c70-9f5f-8acfd1e861a1"
        )
        == "notes-cli"
    )
    assert app_repo_name("widgets (worktree)") == "widgets"
    assert app_repo_name("notes#9") == "notes"
    assert app_repo_name("widgets (admin-reporting)") == "widgets"
    assert app_repo_name("", "widgets") == "widgets"
    assert "#" not in app_repo_name("/Users/me/Documents/GitHub/widgets-issue-9")


def test_project_from_path_pretty_names(tmp_path: Path):
    from grok_build_cli_utilities.utils.usage_tokens import project_from_path

    def _touch(encoded: str) -> Path:
        p = tmp_path / "sessions" / encoded / "sid" / "updates.jsonl"
        p.parent.mkdir(parents=True)
        p.write_text("")
        return p

    wt = (
        "%2FUsers%2Fbrunnr%2F.grok%2Fworktrees%2Fgithub-grok-build-cli-utilities"
        "%2Fsubagent-01a05ed6-818e-7c70-9f5f-8acfd1e861a1"
    )
    short, cwd = project_from_path(_touch(wt))
    assert short == "grok-build-cli-utilities (worktree)"
    assert cwd.endswith("subagent-01a05ed6-818e-7c70-9f5f-8acfd1e861a1")

    issue = "%2FUsers%2Fbrunnr%2FDocuments%2FGitHub%2Fnotes-issue-9"
    short, _cwd = project_from_path(_touch(issue))
    assert short == "notes#9"

    parent = "%2FUsers%2Fbrunnr%2FDocuments%2FGitHub%2Fnotes"
    short, _cwd = project_from_path(_touch(parent))
    assert short == "notes"


def test_disambiguate_display_keys_collision_suffix():
    from grok_build_cli_utilities.utils.usage_tokens import disambiguate_display_keys

    uniq = disambiguate_display_keys(["a", "b"], ["widgets #12,15", "notes#9"])
    assert uniq == ["widgets #12,15", "notes#9"]
    collided = disambiguate_display_keys(
        ["01a05e3c-deadbeef", "01a05e3d-cafe"],
        ["notes#22", "notes#22"],
    )
    assert collided == [
        "notes#22 · 01a05e3c…",
        "notes#22 · 01a05e3d…",
    ]


def test_pr_group_key_mixed_compact():
    from grok_build_cli_utilities.utils.usage_tokens import CreatedPr, pr_group_key

    mixed = [
        CreatedPr("example", "widgets", pr=80, issue=7),
        CreatedPr("example", "widgets", pr=81, issue=8),
        CreatedPr("example", "widgets", pr=82, issue=14),
        CreatedPr("example", "notes", pr=15, issue=None),
    ]
    assert pr_group_key("sid", mixed) == "widgets #7,8,14 · notes #15"


def test_usage_cost_by_app_rolls_up_worktrees(tmp_path: Path):
    grok = tmp_path / ".grok"
    paths = {
        ("%2FUsers%2Fme%2FDocuments%2FGitHub%2Fwidgets"): 1_000_000_000,
        (
            "%2FUsers%2Fme%2F.grok%2Fworktrees%2Fgithub-widgets"
            "%2Fsubagent-01a05ed6-818e-7c70-9f5f-8acfd1e861a1"
        ): 2_000_000_000,
        "%2FUsers%2Fme%2FDocuments%2FGitHub%2Fnotes-issue-9": 3_000_000_000,
        "%2FUsers%2Fme%2FDocuments%2FGitHub%2Fwidgets-issue-79": 4_000_000_000,
    }
    for i, (encoded, ticks) in enumerate(paths.items()):
        _write_turn(
            grok / "sessions" / encoded / f"s{i}" / "updates.jsonl",
            prompt_id=f"p{i}",
            ts="2026-08-02T12:00:00Z",
            input_t=100,
            output_t=1,
            cached=0,
            reasoning=0,
            ticks=ticks,
        )
    data = _json_from_cli(
        runner.invoke(
            app,
            [
                "-g",
                str(grok),
                "usage",
                "cost",
                "--from",
                "2026-08-01",
                "--to",
                "2026-08-05",
                "--by",
                "app",
                "--json",
            ],
        )
    )
    by_key = {b["key"]: b for b in data["buckets"]}
    assert set(by_key) == {"widgets", "notes"}
    assert by_key["widgets"]["prompts"] == 3
    assert by_key["notes"]["prompts"] == 1
    assert "notes#9" not in by_key
    assert "widgets#79" not in by_key
    assert "widgets (worktree)" not in by_key
    assert not any("#" in k for k in by_key)
    assert not any(k.startswith("subagent-") for k in by_key)


def test_usage_cost_by_app_parent_and_issue_clone_sum(tmp_path: Path):
    grok = tmp_path / ".grok"
    parent = grok / "sessions" / "%2FUsers%2Fme%2FDocuments%2FGitHub%2Fwidgets" / "s1"
    issue = grok / "sessions" / "%2FUsers%2Fme%2Fsrc%2Fwidgets-issue-9" / "s2"
    _write_turn(
        parent / "updates.jsonl",
        prompt_id="p-parent",
        ts="2026-08-02T12:00:00Z",
        input_t=100,
        output_t=1,
        cached=0,
        reasoning=0,
        ticks=1_000_000_000,
    )
    _write_turn(
        issue / "updates.jsonl",
        prompt_id="p-issue",
        ts="2026-08-02T13:00:00Z",
        input_t=200,
        output_t=2,
        cached=0,
        reasoning=0,
        ticks=2_000_000_000,
    )
    args = [
        "-g",
        str(grok),
        "usage",
        "cost",
        "--from",
        "2026-08-01",
        "--to",
        "2026-08-05",
        "--json",
    ]
    by_app = _json_from_cli(runner.invoke(app, [*args, "--by", "app"]))
    assert len(by_app["buckets"]) == 1
    row = by_app["buckets"][0]
    assert row["key"] == "widgets"
    assert row["prompts"] == 2
    assert abs(row["list_usd"] - 0.3) < 1e-6
    by_project = _json_from_cli(runner.invoke(app, [*args, "--by", "project"]))
    assert len(by_project["buckets"]) == 2
    by_sess = _json_from_cli(runner.invoke(app, [*args, "--by", "session"]))
    assert len(by_sess["buckets"]) == 2


def test_usage_cost_by_app_case_merge_prefers_github_spelling(tmp_path: Path):
    grok = tmp_path / ".grok"
    _write_turn(
        grok
        / "sessions"
        / "%2FUsers%2Fme%2F.grok%2Fworktrees%2Fgithub-widgets%2Fsubagent-aa"
        / "s1"
        / "updates.jsonl",
        prompt_id="p-wt",
        ts="2026-08-02T12:00:00Z",
        input_t=100,
        output_t=1,
        cached=0,
        reasoning=0,
        ticks=1_000_000_000,
    )
    _write_turn(
        grok / "sessions" / "%2FUsers%2Fme%2FDocuments%2FGitHub%2FWidgets" / "s2" / "updates.jsonl",
        prompt_id="p-gh",
        ts="2026-08-02T13:00:00Z",
        input_t=100,
        output_t=1,
        cached=0,
        reasoning=0,
        ticks=2_000_000_000,
    )
    data = _json_from_cli(
        runner.invoke(
            app,
            [
                "-g",
                str(grok),
                "usage",
                "cost",
                "--from",
                "2026-08-01",
                "--to",
                "2026-08-05",
                "--by",
                "app",
                "--json",
            ],
        )
    )
    assert [b["key"] for b in data["buckets"]] == ["Widgets"]
    assert data["buckets"][0]["prompts"] == 2
    assert abs(data["buckets"][0]["list_usd"] - 0.3) < 1e-6


def test_load_keeps_pretty_project_for_unlabeled_session(tmp_path: Path):
    from grok_build_cli_utilities.utils.usage_tokens import (
        aggregate,
        load_turn_usage,
        session_display_key,
    )

    sess = (
        tmp_path
        / "sessions"
        / "%2FUsers%2Fme%2FDocuments%2FGitHub%2Fnotes-issue-9"
        / "sid1"
        / "updates.jsonl"
    )
    _write_turn(
        sess,
        prompt_id="p1",
        ts="2026-08-02T12:00:00Z",
        input_t=100,
        output_t=1,
        cached=0,
        reasoning=0,
        ticks=1,
    )
    recs = load_turn_usage(tmp_path / "sessions")
    assert recs[0].project == "notes#9"
    assert aggregate(recs, "app")[0].key == "notes"
    assert session_display_key(recs[0].session_id, [], project=recs[0].project) == "notes#9"


def test_usage_cost_by_pr_prints_unsplit_note(tmp_path: Path):
    from grok_build_cli_utilities.utils.usage_tokens import UNSPLIT_MULTI_PR_NOTE

    grok = tmp_path / ".grok"
    sid = "01a059cb-5e07-7893-aab3-bad45b49c8ab"
    upd = grok / "sessions" / "widgets" / sid / "updates.jsonl"
    _write_turn(
        upd,
        prompt_id="p1",
        ts="2026-08-02T12:00:00Z",
        input_t=100,
        output_t=10,
        cached=0,
        reasoning=0,
        ticks=8_000_000_000,
    )
    _append_update(upd, _mcp_create_pr_update(session_id=sid, number=70))
    _append_update(upd, _mcp_create_pr_update(session_id=sid, number=72, ts="2026-08-02T13:00:00Z"))
    r = runner.invoke(
        app,
        [
            "-g",
            str(grok),
            "usage",
            "cost",
            "--from",
            "2026-08-01",
            "--to",
            "2026-08-05",
            "--by",
            "pr",
        ],
    )
    assert r.exit_code == 0, r.output
    blob = r.output + (r.stdout or "")
    assert UNSPLIT_MULTI_PR_NOTE in blob
    assert "widgets #70,72" in blob


def _late_et_turn(tmp_path: Path) -> Path:
    """Turn at 11:51 PM ET 2026-09-01, stored as 2026-09-02T03:51:00Z."""
    grok = tmp_path / ".grok"
    sess = grok / "sessions" / "notes" / "s1"
    _write_turn(
        sess / "updates.jsonl",
        prompt_id="p1",
        ts="2026-09-02T03:51:00Z",
        input_t=100,
        output_t=10,
        cached=0,
        reasoning=0,
        ticks=1_000_000_000,
    )
    return grok


def test_filter_usage_local_calendar_not_utc_date():
    from zoneinfo import ZoneInfo

    rec = UsageRec(
        prompt_id="p1",
        ts=datetime(2026, 9, 2, 3, 51, tzinfo=timezone.utc),
        project="notes",
        cwd="/notes",
        session_id="s1",
    )
    ny = ZoneInfo("America/New_York")
    assert filter_usage([rec], date_from=date(2026, 9, 2), tz=ny) == []
    assert filter_usage([rec], date_from=date(2026, 9, 1), tz=ny) == [rec]
    assert filter_usage([rec], date_from=date(2026, 9, 2), tz=timezone.utc) == [rec]


def test_bucket_key_day_matches_filter_zone():
    from zoneinfo import ZoneInfo

    rec = UsageRec(
        prompt_id="p1",
        ts=datetime(2026, 9, 2, 3, 51, tzinfo=timezone.utc),
        project="notes",
        cwd="/notes",
        session_id="s1",
    )
    ny = ZoneInfo("America/New_York")
    assert bucket_key(rec, "day", tz=ny) == "2026-09-01"
    assert bucket_key(rec, "day", tz=timezone.utc) == "2026-09-02"
    assert bucket_key(rec, "month", tz=ny) == "2026-09"


def test_resolve_usage_date_tz_cli_wins_over_config():
    from zoneinfo import ZoneInfo

    _tz, label = resolve_usage_date_tz(cli=None, config=None)
    assert label == "local"
    tz, label = resolve_usage_date_tz(cli=None, config="UTC")
    assert tz is timezone.utc
    assert label == "UTC"
    tz, label = resolve_usage_date_tz(cli="America/New_York", config="UTC")
    assert tz == ZoneInfo("America/New_York")
    assert label == "America/New_York"
    _tz, label = resolve_usage_date_tz(cli="local", config="UTC")
    assert label == "local"


def test_usage_cost_from_local_calendar_excludes_utc_next_day(tmp_path: Path):
    grok = _late_et_turn(tmp_path)
    base = ["-g", str(grok), "usage", "cost", "--json", "--by", "day"]

    ny_next = runner.invoke(app, [*base, "--from", "2026-09-02", "--tz", "America/New_York"])
    assert ny_next.exit_code == 0, ny_next.output
    assert "{" not in (ny_next.stdout or ny_next.output or "")

    ny_same = runner.invoke(app, [*base, "--from", "2026-09-01", "--tz", "America/New_York"])
    data = _json_from_cli(ny_same)
    assert data["date_tz"] == "America/New_York"
    assert data["totals"]["prompts"] == 1
    assert data["buckets"][0]["key"] == "2026-09-01"
    assert data["result_from"] == "2026-09-01"

    utc = runner.invoke(app, [*base, "--from", "2026-09-02", "--tz", "UTC"])
    data = _json_from_cli(utc)
    assert data["date_tz"] == "UTC"
    assert data["totals"]["prompts"] == 1
    assert data["buckets"][0]["key"] == "2026-09-02"
    assert data["result_from"] == "2026-09-02"


def test_usage_report_from_local_calendar_and_date_tz_json(tmp_path: Path):
    grok = _late_et_turn(tmp_path)
    r = runner.invoke(
        app,
        [
            "-g",
            str(grok),
            "usage",
            "report",
            "--from",
            "2026-09-02",
            "--tz",
            "America/New_York",
            "--json",
        ],
    )
    assert r.exit_code == 0, r.output
    assert "{" not in (r.stdout or r.output or "")

    r2 = runner.invoke(
        app,
        [
            "-g",
            str(grok),
            "usage",
            "report",
            "--from",
            "2026-09-02",
            "--tz",
            "UTC",
            "--json",
        ],
    )
    data = _json_from_cli(r2)
    assert data["date_tz"] == "UTC"
    assert data["totals"]["prompts"] == 1


def test_usage_date_tz_config_and_cli_override(tmp_path: Path):
    grok = _late_et_turn(tmp_path)
    (grok / "grok-utils.toml").write_text('[usage]\ndate_tz = "UTC"\n', encoding="utf-8")
    r = runner.invoke(
        app,
        ["-g", str(grok), "usage", "cost", "--from", "2026-09-02", "--json"],
    )
    data = _json_from_cli(r)
    assert data["date_tz"] == "UTC"
    assert data["totals"]["prompts"] == 1

    r2 = runner.invoke(
        app,
        [
            "-g",
            str(grok),
            "usage",
            "cost",
            "--from",
            "2026-09-02",
            "--tz",
            "America/New_York",
            "--json",
        ],
    )
    assert r2.exit_code == 0, r2.output
    assert "{" not in (r2.stdout or r2.output or "")


def test_usage_cost_default_date_tz_is_local(tmp_path: Path):
    grok = _late_et_turn(tmp_path)
    r = runner.invoke(
        app,
        ["-g", str(grok), "usage", "cost", "--from", "2026-09-01", "--to", "2026-09-02", "--json"],
    )
    data = _json_from_cli(r)
    assert data["date_tz"] == "local"
    assert data["totals"]["prompts"] == 1


def test_usage_unknown_tz_exits(tmp_path: Path):
    r = runner.invoke(
        app,
        [
            "-g",
            str(tmp_path / ".grok"),
            "usage",
            "cost",
            "--from",
            "2026-09-01",
            "--tz",
            "Not/AZone",
        ],
    )
    assert r.exit_code != 0
    blob = (r.output or "") + (r.stderr or "")
    assert "Not/AZone" in blob


def test_usage_cost_help_from_is_local_calendar():
    r = runner.invoke(app, ["usage", "cost", "--help"])
    assert r.exit_code == 0, r.output
    blob = _plain_cli(r.output).lower()
    assert "local calendar" in blob
    assert "--tz" in blob
    assert "utc" in blob
    assert "iana" in blob
    assert "date_tz" in blob
    assert "--all" in blob
    assert "overrides" in blob
    assert "default: 10" in blob
    r2 = runner.invoke(app, ["usage", "report", "--help"])
    assert r2.exit_code == 0, r2.output
    blob2 = _plain_cli(r2.output).lower()
    assert "local calendar" in blob2
    assert "--tz" in blob2
    assert "iana" in blob2
    assert "--all" in blob2
    assert "default: 10" in blob2


def test_usage_info_explains_local_from():
    r = runner.invoke(app, ["usage", "info"])
    assert r.exit_code == 0, r.output
    assert "Why is --from a local date?" in r.output
    assert "--tz UTC" in r.output
    assert "weekly pool resets" in r.output.lower() or "Weekly pool resets" in r.output
    assert "Default is top 10 by list$" in r.output
    assert "--all prints every row" in r.output
    assert "TOTALS is the whole window" in r.output
    assert "--all to see all" in r.output


def test_shown_bucket_count_all_overrides_top():
    from grok_build_cli_utilities.utils.usage_display import (
        DEFAULT_BUCKET_TOP,
        bucket_cut_caption,
        shown_bucket_count,
    )

    assert DEFAULT_BUCKET_TOP == 10
    assert shown_bucket_count(18, top=10, show_all=False) == 10
    assert shown_bucket_count(18, top=3, show_all=True) == 18
    assert shown_bucket_count(18, top=0, show_all=False) == 0
    assert shown_bucket_count(18, top=0, show_all=True) == 18
    assert shown_bucket_count(5, top=10, show_all=False) == 5
    assert shown_bucket_count(5, top=-1, show_all=False) == 0
    assert bucket_cut_caption(10, 18) == "top 10 of 18"
    assert bucket_cut_caption(10, 10) == "all 10"
    assert bucket_cut_caption(12, 12) == "all 12"


def _write_ranked_apps(grok: Path, n: int = 12) -> list[str]:
    names = [f"bucket{i:02d}" for i in range(n)]
    ticks_per_usd = 10_000_000_000
    for i, name in enumerate(names):
        sess = grok / "sessions" / name / f"s{i:02d}"
        _write_turn(
            sess / "updates.jsonl",
            prompt_id=f"p{i:02d}",
            ts="2026-08-02T12:00:00Z",
            input_t=1000,
            output_t=10,
            cached=0,
            reasoning=0,
            ticks=(n - i) * ticks_per_usd,
        )
    return names


def test_usage_cost_default_top_10_caption_and_no_fold(tmp_path: Path):
    grok = tmp_path / ".grok"
    names = _write_ranked_apps(grok, 12)
    args = [
        "-g",
        str(grok),
        "usage",
        "cost",
        "--from",
        "2026-08-01",
        "--by",
        "app",
    ]
    human = runner.invoke(app, args)
    assert human.exit_code == 0, human.output
    out = human.output
    assert "top 10 of 12" in out
    assert "TOTALS is the whole window" in out
    assert "--all" in out
    assert "to see all" in out
    assert "list$=$78.00" in out or "list$=$78.00" in _plain_cli(out)
    assert names[0] in out
    assert names[9] in out
    assert names[10] not in out
    assert names[11] not in out

    js = runner.invoke(app, [*args, "--json"])
    assert js.exit_code == 0, js.output
    data = _json_from_cli(js)
    keys = [b["key"] for b in data["buckets"]]
    assert len(keys) == 10
    assert keys == names[:10]
    assert names[10] not in keys
    assert names[11] not in keys
    assert abs(data["totals"]["list_usd"] - 78.0) < 1e-6
    shown_sum = sum(b["list_usd"] for b in data["buckets"])
    assert abs(shown_sum - 75.0) < 1e-6
    assert abs(data["totals"]["list_usd"] - shown_sum) > 1.0


def test_usage_cost_all_overrides_top(tmp_path: Path):
    grok = tmp_path / ".grok"
    names = _write_ranked_apps(grok, 12)
    args = [
        "-g",
        str(grok),
        "usage",
        "cost",
        "--from",
        "2026-08-01",
        "--by",
        "app",
        "--all",
        "--top",
        "3",
    ]
    human = runner.invoke(app, args)
    assert human.exit_code == 0, human.output
    out = human.output
    assert "all 12" in out
    assert "top 10 of" not in out
    assert "to see all" not in out
    assert names[11] in out
    js = runner.invoke(app, [*args, "--json"])
    assert js.exit_code == 0, js.output
    data = _json_from_cli(js)
    keys = [b["key"] for b in data["buckets"]]
    assert len(keys) == 12
    assert keys == names
    assert abs(data["totals"]["list_usd"] - 78.0) < 1e-6


def test_usage_cost_top_zero_shows_none(tmp_path: Path):
    grok = tmp_path / ".grok"
    _write_ranked_apps(grok, 12)
    r = runner.invoke(
        app,
        [
            "-g",
            str(grok),
            "usage",
            "cost",
            "--from",
            "2026-08-01",
            "--by",
            "app",
            "--top",
            "0",
            "--json",
        ],
    )
    assert r.exit_code == 0, r.output
    data = _json_from_cli(r)
    assert data["buckets"] == []
    assert abs(data["totals"]["list_usd"] - 78.0) < 1e-6


def test_usage_report_default_top_and_all(tmp_path: Path):
    grok = tmp_path / ".grok"
    names = _write_ranked_apps(grok, 12)
    args = [
        "-g",
        str(grok),
        "usage",
        "report",
        "--from",
        "2026-08-01",
        "--by",
        "app",
    ]
    human = runner.invoke(app, args)
    assert human.exit_code == 0, human.output
    assert "top 10 of 12" in human.output
    assert "--all" in human.output
    assert names[11] not in human.output
    all_human = runner.invoke(app, [*args, "--all"])
    assert all_human.exit_code == 0, all_human.output
    assert "all 12" in all_human.output
    assert "to see all" not in all_human.output
    assert names[11] in all_human.output
    js = runner.invoke(app, [*args, "--json"])
    assert js.exit_code == 0, js.output
    data = _json_from_cli(js)
    assert len(data["buckets"]) == 10
    all_js = runner.invoke(app, [*args, "--all", "--json"])
    assert all_js.exit_code == 0, all_js.output
    assert len(_json_from_cli(all_js)["buckets"]) == 12
