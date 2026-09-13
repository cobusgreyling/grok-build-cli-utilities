"""Shared token-cost window builder for usage cost + token report.

One pipeline: load records → billing/auth context → auth-mix (optional per-key
est$) → totals. Command modules only render.
"""

from __future__ import annotations

from dataclasses import dataclass
from collections.abc import Iterable, Mapping
from datetime import date, datetime, tzinfo
from pathlib import Path
from typing import Any

from .auth_status import (
    AuthStatus,
    auth_history_change_points,
    detect_auth,
    load_auth_history,
    load_billing_snapshot,
)
from .pricing import (
    AuthMixResult,
    TokenRates,
    apply_cash_scale,
    apply_topoff_discount,
    estimate_with_auth_mix,
    load_usage_config,
    resolve_cash_scale,
    resolve_rates_model,
    resolve_topoff_discount,
)
from .usage_tokens import (
    CreatedPr,
    UsageBucket,
    UsageRec,
    aggregate,
    bucket_key,
    preferred_app_names,
    total_bucket,
)


@dataclass
class TokenCostWindow:
    """Computed list$/est$ window ready for table + footer rendering."""

    records: list[UsageRec]
    buckets: list[UsageBucket]
    tot: UsageBucket
    list_total: float
    est_total: float
    est_cash_total: float
    est_by_key: dict[str, float]
    mix: AuthMixResult
    cash_scale_val: float
    cash_scale_src: str
    force_uniform: float | None
    force_src: str | None
    topoff_d: float
    topoff_src: str
    auth_st: AuthStatus
    weekly_pct: float | None
    prepaid_balance: float | None
    subscription_tier: str | None  # heavy | supergrok | None
    subscription_tier_raw: str | None
    weekly_period_start: datetime | None
    weekly_period_end: datetime | None
    window_tiers: list[str]
    usage_cfg: dict[str, Any]
    rates: TokenRates
    rates_label: str
    list_source: str  # "ticks" | "rates"
    prefer_ticks: bool
    group: str
    d_from: date | None
    d_to: date | None
    result_earliest: date | None
    result_latest: date | None
    data_earliest: date | None
    data_latest: date | None

    def est_for_key(self, key: str) -> float:
        """est$ for a bucket key (0 if empty)."""
        return float(self.est_by_key.get(key, 0.0))

    def list_for_key(self, key: str) -> float:
        """list$ for a bucket key (auth-mix total; 0 if empty)."""
        return float(self.mix.list_by_key.get(key, 0.0))


def build_token_cost_window(
    grok_home: Path | str,
    records: list[UsageRec],
    *,
    group: str,
    rates_model: str | None = None,
    cash_scale: float | None = None,
    prepaid_usd: float | None = None,
    credits_remaining: float | None = None,
    topoff_discount: float | None = None,
    d_from: date | None = None,
    d_to: date | None = None,
    data_earliest: date | None = None,
    data_latest: date | None = None,
    result_earliest: date | None = None,
    result_latest: date | None = None,
    prs_by_session: Mapping[str, Iterable[CreatedPr | str]] | None = None,
    include_unlabeled: bool = False,
    date_tz: tzinfo | None = None,
) -> TokenCostWindow:
    """Build list$/est$ for filtered records (shared by cost + report)."""
    # Omit --rates-model → prefer costUsdTicks (same $ as Build /usage Cost).
    # Pass -m to force a reconstructed rate table (ticks ignored).
    prefer_ticks = not (rates_model and str(rates_model).strip())
    rates_label, rates = resolve_rates_model(rates_model)
    usage_cfg = load_usage_config(grok_home)
    auth_st = detect_auth(grok_home)
    billing = load_billing_snapshot(grok_home)
    weekly_pct = billing.weekly_pct
    prepaid_balance = billing.prepaid_usd
    weekly_tl = billing.weekly_timeline
    tier_tl = billing.tier_timeline

    cfg_scale = usage_cfg.get("cash_scale")
    if cfg_scale is not None:
        try:
            cfg_scale = float(cfg_scale)
        except (TypeError, ValueError):
            cfg_scale = None

    app_names = preferred_app_names(records) if group == "app" else None
    buckets = aggregate(
        records,
        group,
        prs_by_session=prs_by_session,
        include_unlabeled=include_unlabeled,
        tz=date_tz,
        app_names=app_names,
    )
    tot = total_bucket(records)
    list_seed = tot.list_usd(rates, prefer_ticks=prefer_ticks)

    force_uniform: float | None = None
    force_src: str | None = None
    if prepaid_usd is not None and credits_remaining is not None and list_seed > 0:
        force_uniform, force_src = resolve_cash_scale(
            prepaid_usd=prepaid_usd,
            credits_remaining=credits_remaining,
            list_total_usd=list_seed,
        )
    elif cash_scale is not None:
        force_uniform, force_src = float(cash_scale), f"cli --cash-scale {cash_scale:g}"
    elif cfg_scale is not None:
        force_uniform, force_src = float(cfg_scale), f"config cash_scale={cfg_scale:g}"

    change_pts = auth_history_change_points(load_auth_history(grok_home))
    fallback = auth_st.effective if auth_st.effective != "none" else "api_key"

    def _gkey(r: UsageRec) -> str:
        k = bucket_key(
            r,
            group,
            prs_by_session=prs_by_session,
            include_unlabeled=include_unlabeled,
            tz=date_tz,
            app_names=app_names,
        )
        return k if k is not None else (r.session_id or "unknown")

    mix = estimate_with_auth_mix(
        records,
        rates,
        change_points=change_pts,
        usage_cfg=usage_cfg,
        weekly_usage_pct=weekly_pct,
        weekly_timeline=weekly_tl,
        tier_timeline=tier_tl,
        fallback_auth=fallback,
        force_uniform_scale=force_uniform,
        force_uniform_src=force_src,
        group_key_fn=_gkey,
        prefer_ticks=prefer_ticks,
    )
    list_total = mix.list_total
    est_total = mix.est_total
    est_by_key = dict(mix.est_by_key)
    list_source = "ticks" if prefer_ticks and tot.ticks > 0 else "rates"

    if force_uniform is not None:
        cash_scale_val, cash_scale_src = force_uniform, force_src or "uniform"
    elif mix.slices:
        top_slice = mix.slices[0]
        cash_scale_val, cash_scale_src = (
            top_slice.scale,
            (f"auth_mix · primary {top_slice.path} @ {top_slice.scale:g}"),
        )
    else:
        cash_scale_val, cash_scale_src = resolve_cash_scale(
            usage_cfg=usage_cfg,
            auth_effective=auth_st.effective,
            weekly_usage_pct=weekly_pct,
        )

    topoff_d, topoff_src = resolve_topoff_discount(usage_cfg, cli_discount=topoff_discount)
    est_cash_total = apply_topoff_discount(est_total, topoff_d)

    # Sort buckets by list$ (activity)
    buckets.sort(key=lambda b: -float(mix.list_by_key.get(b.key, 0.0)))

    window_tiers: list[str] = []
    for s in mix.slices:
        p = str(getattr(s, "path", "") or "")
        if p.startswith("heavy") and "heavy" not in window_tiers:
            window_tiers.append("heavy")
        elif p.startswith("supergrok") and "supergrok" not in window_tiers:
            window_tiers.append("supergrok")
    if billing.subscription_tier and billing.subscription_tier not in window_tiers:
        window_tiers.append(billing.subscription_tier)

    return TokenCostWindow(
        records=records,
        buckets=buckets,
        tot=tot,
        list_total=list_total,
        est_total=est_total,
        est_cash_total=est_cash_total,
        est_by_key=est_by_key,
        mix=mix,
        cash_scale_val=cash_scale_val,
        cash_scale_src=cash_scale_src,
        force_uniform=force_uniform,
        force_src=force_src,
        topoff_d=topoff_d,
        topoff_src=topoff_src,
        auth_st=auth_st,
        weekly_pct=weekly_pct,
        prepaid_balance=prepaid_balance,
        subscription_tier=billing.subscription_tier,
        subscription_tier_raw=billing.subscription_tier_raw,
        weekly_period_start=billing.weekly_period_start,
        weekly_period_end=billing.weekly_period_end,
        window_tiers=window_tiers,
        usage_cfg=usage_cfg,
        rates=rates,
        rates_label=rates_label,
        list_source=list_source,
        prefer_ticks=prefer_ticks,
        group=group,
        d_from=d_from,
        d_to=d_to,
        result_earliest=result_earliest,
        result_latest=result_latest,
        data_earliest=data_earliest,
        data_latest=data_latest,
    )


def api_scale_for_advisor(win: TokenCostWindow) -> tuple[float, float]:
    """Pure-API scale + list$×scale for plan-advisor (never SuperGrok pool 0)."""
    scale_api, _ = resolve_cash_scale(
        usage_cfg=win.usage_cfg,
        auth_effective="api_key",
        weekly_usage_pct=win.weekly_pct,
    )
    return scale_api, apply_cash_scale(win.list_total, scale_api)
