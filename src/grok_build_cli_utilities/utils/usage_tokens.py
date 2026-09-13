"""Turn-level usage from session updates.jsonl (token-accurate cost foundation)."""

from __future__ import annotations

import json
import re
from collections.abc import Iterable, Iterator, Mapping
from dataclasses import dataclass, field
from datetime import date, datetime, timezone, tzinfo
from pathlib import Path
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from rich.progress import Progress

from .pricing import TokenRates, api_estimate_usd, rates_for_model

# xAI / Build: 1 USD = 10^10 costUsdTicks. /usage Session Cost uses this.
# https://docs.x.ai/developers/cost-tracking
TICKS_PER_USD = 10_000_000_000
# Prompt ≥ this many tokens bills the whole request at 2× list rates.
LONG_CONTEXT_PROMPT_TOKENS = 200_000
COST_GROUPS = (
    "app",
    "project",
    "model",
    "day",
    "week",
    "month",
    "session",
    "pr",
    "none",
)
TOKEN_REPORT_GROUPS = ("app", "project", "model", "day", "session", "pr")
_GH_PULL_URL = re.compile(
    r"https://github\.com/([^/\s]+)/([^/\s]+)/pull/(\d+)\b",
    re.IGNORECASE,
)
# GitHub closing keywords only. Do not treat prose "#58" as an issue.
_ISSUE_KW = re.compile(
    r"(?i)\b(?:fix(?:ed|es)?|close[sd]?|resolve[sd]?)\s*:?\s+"
    r"(?:https://github\.com/[^/\s]+/[^/\s]+/issues/|(?:[\w.-]+/[\w.-]+)?#)"
    r"(\d+)\b"
)


@dataclass
class UsageRec:
    """One deduped turn_completed usage record."""

    prompt_id: str
    ts: datetime
    project: str  # short app name
    cwd: str  # decoded path when available
    session_id: str
    model: str = "unknown"
    input: int = 0
    output: int = 0
    total: int = 0
    cached: int = 0
    reasoning: int = 0
    ticks: int = 0
    model_calls: int = 0


@dataclass
class UsageBucket:
    """Aggregate usage for a group key."""

    key: str
    n: int = 0
    input: int = 0
    output: int = 0
    total: int = 0
    cached: int = 0
    reasoning: int = 0
    ticks: int = 0
    model_calls: int = 0
    models: dict[str, int] = field(default_factory=dict)

    def add(self, r: UsageRec) -> None:
        self.n += 1
        self.input += r.input
        self.output += r.output
        self.total += r.total
        self.cached += r.cached
        self.reasoning += r.reasoning
        self.ticks += r.ticks
        self.model_calls += r.model_calls
        if r.model:
            self.models[r.model] = self.models.get(r.model, 0) + 1

    @property
    def uncached_in(self) -> int:
        return max(self.input - self.cached, 0)

    @property
    def cache_pct(self) -> float:
        return (100.0 * self.cached / self.total) if self.total else 0.0

    def primary_model(self) -> str:
        if not self.models:
            return "unknown"
        return max(self.models.items(), key=lambda kv: kv[1])[0]

    def api_est(self, rates: TokenRates | None = None) -> float:
        """Rate-table estimate (no ticks). Prefer ``list_usd`` for /usage-matching $."""
        r = rates or rates_for_model(self.primary_model())
        out_n = completion_tokens(
            output=self.output,
            reasoning=self.reasoning,
            total=self.total,
            input_tokens=self.input,
        )
        return api_estimate_usd(
            cached=self.cached,
            uncached_in=self.uncached_in,
            output=out_n,
            reasoning=0,
            rates=r,
            reason_as_output=False,
        )

    def list_usd(self, rates: TokenRates | None = None, *, prefer_ticks: bool = True) -> float:
        """list$ for this bucket: costUsdTicks/1e10 when present, else rate table."""
        if prefer_ticks and self.ticks > 0:
            return list_price_usd(self.ticks)
        return self.api_est(rates)

    def to_dict(self, rates: TokenRates | None = None) -> dict:
        return {
            "key": self.key,
            "prompts": self.n,
            "input": self.input,
            "cached": self.cached,
            "uncached_in": self.uncached_in,
            "output": self.output,
            "reasoning": self.reasoning,
            "total": self.total,
            "cache_pct": round(self.cache_pct, 2),
            "ticks": self.ticks,
            "model_calls": self.model_calls,
            "primary_model": self.primary_model(),
            "api_est_usd": round(self.api_est(rates), 4),
        }


def parse_ts(obj: dict) -> datetime | None:
    meta = (obj.get("params") or {}).get("_meta") or {}
    ms = meta.get("agentTimestampMs")
    if ms is not None:
        try:
            return datetime.fromtimestamp(float(ms) / 1000.0, tz=timezone.utc)
        except (TypeError, ValueError, OSError):
            pass
    ts = obj.get("timestamp")
    if isinstance(ts, (int, float)):
        try:
            if ts > 1e12:
                return datetime.fromtimestamp(ts / 1000.0, tz=timezone.utc)
            return datetime.fromtimestamp(ts, tz=timezone.utc)
        except (ValueError, OSError):
            return None
    if isinstance(ts, str):
        try:
            return datetime.fromisoformat(ts.replace("Z", "+00:00"))
        except ValueError:
            return None
    return None


_ISSUE_CLONE = re.compile(r"^(.+)-issue-(\d+)$", re.IGNORECASE)
_GROK_WORKTREE = re.compile(
    r"(?:^|/)\.grok/worktrees/github-([^/]+)/([^/]+)/?$",
    re.IGNORECASE,
)
_SUBAGENT_LEAF = re.compile(r"^subagent-", re.IGNORECASE)
_WORKTREE_LABEL = re.compile(r"\s*\(worktree\)\s*$", re.IGNORECASE)
# github-znuttyone-ProfitGuard → ProfitGuard. All-lowercase slugs stay intact.
_OWNER_THEN_REPO = re.compile(r"^[a-z0-9][a-z0-9-]*-([A-Z].+)$")


def pretty_app_name(short: str, cwd: str = "") -> str:
    """Unlabeled --by session Key. Issue clones stay repo#N. Does not roll up to the parent app."""
    src = (short or "").strip()
    text = (cwd or src).replace("\\", "/")
    for cand in (Path(text).name, Path(src).name, src):
        if not cand:
            continue
        m = _ISSUE_CLONE.match(cand)
        if m:
            return f"{m.group(1)}#{m.group(2)}"
    m = _GROK_WORKTREE.search(text)
    if m:
        repo, label = m.group(1), m.group(2)
        if _SUBAGENT_LEAF.match(label):
            return f"{repo} (worktree)"
        return f"{repo} ({label})"
    return src


@dataclass(frozen=True)
class AppRepo:
    """Product/repo inferred from a session cwd. No GitHub API."""

    name: str
    rank: int

    @property
    def group(self) -> str:
        return self.name.casefold()


def _path_parts(raw: str) -> list[str]:
    text = (raw or "").replace("%2F", "/").replace("%2f", "/").replace("\\", "/")
    return [p for p in text.split("/") if p and p != "."]


def _strip_worktree_label(name: str) -> str:
    return _WORKTREE_LABEL.sub("", (name or "").strip()).strip()


def _repo_from_github_slug(slug: str) -> str:
    text = (slug or "").strip()
    if text.lower().startswith("github-"):
        text = text[7:]
    m = _OWNER_THEN_REPO.fullmatch(text)
    if m:
        return m.group(1)
    return text


def app_repo_from_cwd(cwd: str, *, fallback: str = "") -> AppRepo:
    """Infer the product/repo from cwd. Higher rank wins when casefold-merging."""
    parts = _path_parts(cwd)
    for i, part in enumerate(parts):
        if part.casefold() == "github" and i + 1 < len(parts):
            leaf = _strip_worktree_label(parts[i + 1])
            m = _ISSUE_CLONE.match(leaf)
            if m:
                return AppRepo(m.group(1), 30)
            return AppRepo(leaf, 40)
    for part in reversed(parts):
        m = _ISSUE_CLONE.match(_strip_worktree_label(part))
        if m:
            return AppRepo(m.group(1), 30)
    for i, part in enumerate(parts):
        if not part.lower().startswith("github-") or len(part) <= 7:
            continue
        if i > 0 and parts[i - 1].casefold() == "worktrees":
            return AppRepo(_repo_from_github_slug(part), 20)
    leaf = _strip_worktree_label(parts[-1] if parts else fallback)
    if not leaf:
        leaf = _strip_worktree_label(fallback)
    m = _ISSUE_CLONE.match(leaf)
    if m:
        return AppRepo(m.group(1), 0)
    head, sep, num = leaf.rpartition("#")
    if sep and num.isdigit() and head and "/" not in head:
        return AppRepo(head, 0)
    labeled = re.match(r"^(.+?)\s+\([^)]+\)\s*$", leaf)
    if labeled:
        return AppRepo(labeled.group(1), 0)
    return AppRepo(leaf or (fallback or "unknown").strip() or "unknown", 0)


def app_repo_name(cwd: str, short: str = "") -> str:
    """--by app Key: repo inferred from cwd (issue and Grok worktrees roll up)."""
    return app_repo_from_cwd(cwd, fallback=short).name


def _prefer_app_repo(new: AppRepo, old: AppRepo) -> bool:
    if new.rank != old.rank:
        return new.rank > old.rank
    new_mixed = new.name != new.name.lower()
    old_mixed = old.name != old.name.lower()
    if new_mixed != old_mixed:
        return new_mixed
    return False


def preferred_app_names(records: Iterable[UsageRec]) -> dict[str, str]:
    """casefold → display spelling. Prefer GitHub/ folder, then repo-issue-N, then slug."""
    best: dict[str, AppRepo] = {}
    for r in records:
        ident = app_repo_from_cwd(r.cwd or r.project)
        prev = best.get(ident.group)
        if prev is None or _prefer_app_repo(ident, prev):
            best[ident.group] = ident
    return {fold: ident.name for fold, ident in best.items()}


def project_from_path(updates_path: Path) -> tuple[str, str]:
    """Return (short_app_name, decoded_cwd_or_parent)."""
    parent = updates_path.parent.parent
    name = parent.name
    decoded = name.replace("%2F", "/")
    cwd = decoded if decoded.startswith("/") else str(parent)
    if "GitHub/" in decoded:
        short = decoded.split("GitHub/")[-1].rstrip("/")
    else:
        short = Path(decoded).name or name
    return pretty_app_name(short, cwd), cwd


@dataclass(frozen=True)
class CreatedPr:
    """One github create_pull_request / gh pr create success."""

    owner: str
    repo: str
    pr: int
    issue: int | None = None

    @property
    def display_num(self) -> int:
        return int(self.issue) if self.issue is not None else int(self.pr)

    @property
    def identity(self) -> str:
        if self.owner and self.repo:
            return f"{self.owner}/{self.repo}#{int(self.pr)}"
        return f"#{int(self.pr)}"

    @property
    def label(self) -> str:
        """Human id: repo#issue when Fixes is present, else repo#PR. No GitHub owner."""
        n = self.display_num
        if self.repo:
            return f"{self.repo}#{n}"
        return f"#{n}"


def _issue_from_text(*texts: str) -> int | None:
    for t in texts:
        if not t:
            continue
        m = _ISSUE_KW.search(t)
        if m:
            n = int(m.group(1))
            if n > 0:
                return n
    return None


def created_pr_from_label(s: str) -> CreatedPr:
    text = str(s or "").strip()
    left, sep, num = text.rpartition("#")
    pr = int(num) if sep and num.isdigit() else 0
    owner, repo = "", left
    if "/" in left:
        owner, repo = left.split("/", 1)
    return CreatedPr(owner=owner, repo=repo, pr=pr or 0, issue=None)


def _as_created_prs(prs: Iterable[CreatedPr | str]) -> list[CreatedPr]:
    out: list[CreatedPr] = []
    seen: set[str] = set()
    for item in prs:
        p = item if isinstance(item, CreatedPr) else created_pr_from_label(str(item))
        if p.pr <= 0 and p.display_num <= 0:
            continue
        ident = p.identity
        if ident in seen:
            continue
        seen.add(ident)
        out.append(p)
    out.sort(key=lambda p: (p.display_num, p.pr, p.repo.lower(), p.owner.lower()))
    return out


def sorted_pr_labels(labels: Iterable[CreatedPr | str]) -> list[str]:
    return [p.label for p in _as_created_prs(labels)]


def short_session_id(session_id: str, *, n: int = 8) -> str:
    if len(session_id) <= n:
        return session_id
    return session_id[:n] + "…"


def _collision_id(ident: str, *, n: int = 8) -> str:
    s = ident
    if _SUBAGENT_LEAF.match(s):
        s = s.split("-", 1)[1]
    return short_session_id(s, n=n)


def disambiguate_display_keys(idents: list[str], labels: list[str]) -> list[str]:
    """Suffix a short id only when two table rows would share a Key."""
    counts: dict[str, int] = {}
    for lab in labels:
        counts[lab] = counts.get(lab, 0) + 1
    out: list[str] = []
    for ident, lab in zip(idents, labels, strict=True):
        if counts[lab] > 1:
            out.append(f"{lab} · {_collision_id(ident)}")
        else:
            out.append(lab)
    return out


def _compact_pr_key(created: list[CreatedPr]) -> str:
    """Repo #N,N groups, repos ordered by the smallest issue/PR number."""
    by_repo: dict[str, list[int]] = {}
    first: dict[str, int] = {}
    for p in created:
        repo = p.repo or "repo"
        by_repo.setdefault(repo, []).append(int(p.display_num))
        n = int(p.display_num)
        prev = first.get(repo)
        first[repo] = n if prev is None else min(prev, n)
    parts: list[str] = []
    for repo in sorted(by_repo, key=lambda r: (first[r], r.lower())):
        nums = ",".join(str(n) for n in sorted(set(by_repo[repo])))
        parts.append(f"{repo} #{nums}")
    return " · ".join(parts)


def pr_group_key(session_id: str, prs: Iterable[CreatedPr | str]) -> str | None:
    """Table/JSON key for --by pr. Issue and PR numbers in numeric order. Never a session UUID."""
    created = _as_created_prs(prs)
    if not created:
        return None
    if len(created) == 1:
        p = created[0]
        if p.issue is not None and p.issue != p.pr:
            return f"{p.label}→#{p.pr}"
        return p.label
    return _compact_pr_key(created)


def session_display_key(
    session_id: str,
    prs: Iterable[CreatedPr | str],
    *,
    project: str = "",
) -> str:
    """Human table key for --by session. Repo/issues, not a UUID."""
    created = _as_created_prs(prs)
    if created:
        head = pr_group_key(session_id, created)
        if head:
            return head
    app = pretty_app_name((project or "").strip())
    if app:
        return app
    return session_id


UNSPLIT_MULTI_PR_NOTE = "Keys with several PRs are one session; tokens are not split."


def _bare_tool_name(name: str) -> str:
    n = str(name or "").strip()
    if n.startswith("github__"):
        return n[len("github__") :]
    return n


def _as_text(value: object) -> str:
    if value is None:
        return ""
    if isinstance(value, str):
        return value
    if isinstance(value, bytes):
        return value.decode("utf-8", errors="replace")
    if isinstance(value, list):
        if value and all(isinstance(x, int) for x in value[:4]):
            try:
                return bytes(value).decode("utf-8", errors="replace")
            except (TypeError, ValueError):
                pass
        return "\n".join(_as_text(x) for x in value)
    if isinstance(value, dict):
        parts: list[str] = []
        for k in ("OkayOutput", "output_for_prompt", "output", "content"):
            if k in value:
                parts.append(_as_text(value[k]))
        if parts:
            return "\n".join(parts)
        try:
            return json.dumps(value)
        except (TypeError, ValueError):
            return str(value)
    return str(value)


def _pr_from_github_object(obj: dict) -> CreatedPr | None:
    """Top-level GitHub PR JSON only (body text cites other PRs)."""
    number = obj.get("number")
    html_raw = obj.get("html_url")
    html = html_raw if isinstance(html_raw, str) else ""
    owner, repo = "", ""
    m = _GH_PULL_URL.search(html)
    if m:
        owner, repo = m.group(1), m.group(2)
        if number is None:
            number = int(m.group(3))
    if number is None:
        url_raw = obj.get("url")
        api = url_raw if isinstance(url_raw, str) else ""
        am = re.search(r"/repos/([^/]+)/([^/]+)/pulls/(\d+)\b", api)
        if am:
            owner, repo = owner or am.group(1), repo or am.group(2)
            number = int(am.group(3))
    try:
        n = int(number)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return None
    if n <= 0:
        return None
    title = obj.get("title") if isinstance(obj.get("title"), str) else ""
    body = obj.get("body") if isinstance(obj.get("body"), str) else ""
    issue = _issue_from_text(str(body or ""), str(title or ""))
    return CreatedPr(owner=owner, repo=repo, pr=n, issue=issue)


def _pr_from_create_payload(blob: object) -> CreatedPr | None:
    if isinstance(blob, dict):
        if "OkayOutput" in blob:
            return _pr_from_create_payload(blob.get("OkayOutput"))
        if "number" in blob or "html_url" in blob:
            return _pr_from_github_object(blob)
        inner = blob.get("output") if isinstance(blob.get("output"), (dict, str)) else None
        if inner is not None:
            return _pr_from_create_payload(inner)
        return None
    if not isinstance(blob, str) or not blob.strip():
        return None
    text = blob.strip()
    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        data = None
    if isinstance(data, dict):
        return _pr_from_create_payload(data)
    return None


def _mcp_tool_name(update: dict) -> str:
    raw = update.get("rawOutput")
    if isinstance(raw, dict):
        name = str(raw.get("tool_name") or "")
        if name:
            return name
    title = str(update.get("title") or "")
    if title:
        return title
    raw_in = update.get("rawInput")
    if isinstance(raw_in, dict):
        return str(raw_in.get("tool_name") or "")
    return ""


def _bash_command(update: dict) -> str:
    raw = update.get("rawOutput")
    if isinstance(raw, dict):
        cmd = raw.get("command")
        if isinstance(cmd, str) and cmd:
            return cmd
    raw_in = update.get("rawInput")
    if isinstance(raw_in, dict):
        cmd = raw_in.get("command")
        if isinstance(cmd, str) and cmd:
            return cmd
    title = str(update.get("title") or "")
    return title


def _bash_stdout(raw: object) -> str:
    if not isinstance(raw, dict):
        return _as_text(raw)
    parts: list[str] = []
    for k in ("output_for_prompt", "output"):
        if k in raw:
            parts.append(_as_text(raw[k]))
    return "\n".join(parts)


def _prs_from_gh_stdout(stdout: str) -> list[CreatedPr]:
    found: list[CreatedPr] = []
    seen: set[str] = set()
    for m in _GH_PULL_URL.finditer(stdout or ""):
        p = CreatedPr(owner=m.group(1), repo=m.group(2), pr=int(m.group(3)))
        if p.identity not in seen:
            seen.add(p.identity)
            found.append(p)
    return found


def pr_creates_from_update(update: dict) -> list[CreatedPr]:
    """Created PRs from a completed create_pull_request or ``gh pr create`` update."""
    if not isinstance(update, dict):
        return []
    if update.get("sessionUpdate") != "tool_call_update":
        return []
    status = update.get("status")
    if status not in (None, "", "completed"):
        return []
    raw = update.get("rawOutput")
    bare = _bare_tool_name(_mcp_tool_name(update))
    if bare == "create_pull_request":
        payload: object
        if isinstance(raw, dict):
            payload = raw.get("output", raw)
        else:
            payload = raw
        pr = _pr_from_create_payload(payload)
        return [pr] if pr else []
    if bare and bare != "create_pull_request":
        if "gh pr create" not in _bash_command(update):
            return []
    cmd = _bash_command(update)
    if "gh pr create" in cmd:
        created = _prs_from_gh_stdout(_bash_stdout(raw))
        issue = _issue_from_text(cmd)
        if issue is not None and len(created) == 1:
            p = created[0]
            created = [CreatedPr(owner=p.owner, repo=p.repo, pr=p.pr, issue=issue)]
        return created
    if isinstance(raw, str) and "create_pull_request_review" not in raw:
        if "create_pull_request" in raw or "OkayOutput" in raw:
            pr = _pr_from_create_payload(raw)
            return [pr] if pr else []
    return []


def pr_labels_from_update(update: dict) -> list[str]:
    """Display labels from a completed create_pull_request or ``gh pr create`` update."""
    return [p.label for p in pr_creates_from_update(update)]


def scan_pr_creates(updates_path: Path) -> set[str]:
    """Created PR labels in one updates.jsonl (create_pull_request / gh pr create only)."""
    found: set[str] = set()
    try:
        f = updates_path.open("r", encoding="utf-8", errors="ignore")
    except OSError:
        return found
    with f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                obj = json.loads(line)
            except json.JSONDecodeError:
                continue
            params = obj.get("params") or {}
            update = params.get("update") or {}
            found.update(pr_labels_from_update(update))
    return found


def _remember_prs(
    dest: dict[str, dict[str, CreatedPr]],
    session_ids: Iterable[str],
    prs: Iterable[CreatedPr],
) -> None:
    created = [p for p in prs if p.pr > 0]
    if not created:
        return
    for sid in session_ids:
        if not sid:
            continue
        bucket = dest.setdefault(sid, {})
        for p in created:
            prev = bucket.get(p.identity)
            if prev is None or (prev.issue is None and p.issue is not None):
                bucket[p.identity] = p


def _primary_model_from_usage(usage: dict) -> str:
    mu = usage.get("modelUsage")
    if isinstance(mu, dict) and mu:
        # Prefer model with highest totalTokens
        best = None
        best_tot = -1
        for mid, stats in mu.items():
            if not isinstance(stats, dict):
                continue
            tot = int(stats.get("totalTokens") or 0)
            if tot >= best_tot:
                best_tot = tot
                best = str(mid)
        if best:
            return best
    return "unknown"


def iter_turn_usage_files(sessions_dir: Path) -> Iterator[Path]:
    if not sessions_dir.is_dir():
        return
    yield from sessions_dir.rglob("updates.jsonl")


def load_turn_usage(
    sessions_dir: Path,
    *,
    progress: Progress | None = None,
    prs_by_session: dict[str, dict[str, CreatedPr]] | None = None,
) -> list[UsageRec]:
    """Load and dedupe turn_completed usage events from all sessions.

    When ``prs_by_session`` is passed, fill it with created PRs per session
    (github ``create_pull_request`` / ``gh pr create`` only). Inner map is
    identity (owner/repo#PR) -> CreatedPr.
    """
    paths = list(iter_turn_usage_files(sessions_dir))
    task = None
    if progress and paths:
        task = progress.add_task("Scanning turn usage...", total=len(paths))

    by_prompt: dict[str, UsageRec] = {}
    prs = prs_by_session
    for path in paths:
        project, cwd = project_from_path(path)
        session_fallback = path.parent.name
        try:
            f = path.open("r", encoding="utf-8", errors="ignore")
        except OSError:
            if progress and task is not None:
                progress.advance(task)
            continue
        with f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    obj = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if obj.get("method") not in ("session/update", "_x.ai/session/update"):
                    continue
                params = obj.get("params") or {}
                update = params.get("update") or {}
                if prs is not None:
                    created = pr_creates_from_update(update)
                    if created:
                        sid = str(params.get("sessionId") or session_fallback)
                        _remember_prs(prs, (sid, session_fallback), created)
                if update.get("sessionUpdate") != "turn_completed":
                    continue
                usage = update.get("usage")
                if not isinstance(usage, dict) or "inputTokens" not in usage:
                    continue
                ts = parse_ts(obj)
                if ts is None:
                    continue
                session_id = str(params.get("sessionId") or session_fallback)
                prompt_id = str(
                    update.get("prompt_id")
                    or update.get("promptId")
                    or f"{session_id}:{obj.get('timestamp')}"
                )
                rec = UsageRec(
                    prompt_id=prompt_id,
                    ts=ts,
                    project=project,
                    cwd=cwd,
                    session_id=session_id,
                    model=_primary_model_from_usage(usage),
                    input=int(usage.get("inputTokens") or 0),
                    output=int(usage.get("outputTokens") or 0),
                    total=int(usage.get("totalTokens") or 0),
                    cached=int(usage.get("cachedReadTokens") or 0),
                    reasoning=int(usage.get("reasoningTokens") or 0),
                    ticks=int(usage.get("costUsdTicks") or 0),
                    model_calls=int(usage.get("modelCalls") or 0),
                )
                prev = by_prompt.get(rec.prompt_id)
                if prev is None or rec.total >= prev.total:
                    by_prompt[rec.prompt_id] = rec
        if progress and task is not None:
            progress.advance(task)

    return sorted(by_prompt.values(), key=lambda r: r.ts)


def local_tz() -> tzinfo:
    """Process-local zone (the machine in front of you)."""
    tz = datetime.now().astimezone().tzinfo
    return tz if tz is not None else timezone.utc


def parse_date_tz(name: str) -> tzinfo:
    """Parse ``local``, ``UTC``, or an IANA zone name."""
    key = name.strip()
    if not key or key.lower() == "local":
        return local_tz()
    if key.upper() == "UTC":
        return timezone.utc
    try:
        return ZoneInfo(key)
    except (ZoneInfoNotFoundError, KeyError, ValueError) as exc:
        raise ValueError(
            f"unknown timezone {name!r} (use local, UTC, or an IANA name such as America/New_York)"
        ) from exc


def date_tz_label(raw: str | None) -> str:
    """Stable JSON/help label for the calendar zone that was requested."""
    if raw is None:
        return "local"
    key = raw.strip()
    if not key or key.lower() == "local":
        return "local"
    if key.upper() == "UTC":
        return "UTC"
    return key


def resolve_usage_date_tz(
    *,
    cli: str | None = None,
    config: str | None = None,
) -> tuple[tzinfo, str]:
    """CLI ``--tz`` wins over ``[usage] date_tz``. Default is local."""
    chosen: str | None = None
    if isinstance(cli, str) and cli.strip():
        chosen = cli
    elif isinstance(config, str) and config.strip():
        chosen = config
    return parse_date_tz(chosen or "local"), date_tz_label(chosen)


def usage_local_dt(ts: datetime, tz: tzinfo) -> datetime:
    """Convert a turn timestamp into the usage calendar zone."""
    aware = ts if ts.tzinfo is not None else ts.replace(tzinfo=timezone.utc)
    return aware.astimezone(tz)


def usage_calendar_date(ts: datetime, tz: tzinfo) -> date:
    """Calendar date of a turn in the usage zone. Do not use UTC ``.date()``."""
    return usage_local_dt(ts, tz).date()


def filter_usage(
    records: list[UsageRec],
    *,
    date_from: date | None = None,
    date_to: date | None = None,
    apps: list[str] | None = None,
    tz: tzinfo | None = None,
) -> list[UsageRec]:
    zone = tz if tz is not None else local_tz()
    out: list[UsageRec] = []
    needles = [a.lower() for a in apps] if apps else None
    for r in records:
        d = usage_calendar_date(r.ts, zone)
        if date_from is not None and d < date_from:
            continue
        if date_to is not None and d > date_to:
            continue
        if needles is not None:
            pl = r.project.lower()
            cl = r.cwd.lower()
            if not any(n in pl or n in cl or pl in n for n in needles):
                continue
        out.append(r)
    return out


def bucket_key(
    r: UsageRec,
    group: str,
    *,
    prs_by_session: Mapping[str, Iterable[CreatedPr | str]] | None = None,
    include_unlabeled: bool = False,
    tz: tzinfo | None = None,
    app_names: Mapping[str, str] | None = None,
) -> str | None:
    if group == "app":
        ident = app_repo_from_cwd(r.cwd or r.project)
        if app_names:
            return app_names.get(ident.group, ident.name)
        return ident.name
    if group == "project":
        return r.cwd or r.project
    if group == "model":
        return r.model or "unknown"
    if group in ("day", "week", "month"):
        local = usage_local_dt(r.ts, tz if tz is not None else local_tz())
        if group == "day":
            return local.date().isoformat()
        if group == "week":
            iso = local.isocalendar()
            return f"{iso.year}-W{iso.week:02d}"
        return f"{local.year}-{local.month:02d}"
    if group == "session":
        return r.session_id or "unknown"
    if group == "pr":
        created = _as_created_prs((prs_by_session or {}).get(r.session_id, ()))
        key = pr_group_key(r.session_id or "unknown", created)
        if key is None and include_unlabeled:
            return r.session_id or "unknown"
        return key
    if group == "none":
        return "all"
    raise ValueError(f"Unknown group: {group}")


def aggregate(
    records: list[UsageRec],
    group: str,
    *,
    prs_by_session: Mapping[str, Iterable[CreatedPr | str]] | None = None,
    include_unlabeled: bool = False,
    tz: tzinfo | None = None,
    app_names: Mapping[str, str] | None = None,
) -> list[UsageBucket]:
    zone = tz if tz is not None else local_tz()
    names = app_names
    if group == "app" and names is None:
        names = preferred_app_names(records)
    m: dict[str, UsageBucket] = {}
    for r in records:
        k = bucket_key(
            r,
            group,
            prs_by_session=prs_by_session,
            include_unlabeled=include_unlabeled,
            tz=zone,
            app_names=names,
        )
        if k is None:
            continue
        if k not in m:
            m[k] = UsageBucket(key=k)
        m[k].add(r)
    return [m[k] for k in sorted(m.keys())]


def total_bucket(records: list[UsageRec]) -> UsageBucket:
    t = UsageBucket(key="TOTAL")
    for r in records:
        t.add(r)
    return t


def allocate_invoice(
    buckets: list[UsageBucket],
    *,
    invoice_usd: float,
    fixed_usd: float = 0.0,
    group: str = "app",
    date_from: date | None = None,
    date_to: date | None = None,
) -> tuple[float, float]:
    """Return (scale_per_tick, fixed_per_bucket).

    var$ = ticks * scale; tot$ = var$ + fixed_per_bucket.
    """
    total_ticks = sum(b.ticks for b in buckets)
    if total_ticks <= 0:
        return 0.0, 0.0
    scale = float(invoice_usd) / total_ticks
    if group == "day" and date_from and date_to:
        n_cal = (date_to - date_from).days + 1
        fixed_per = float(fixed_usd) / n_cal if n_cal else 0.0
    else:
        fixed_per = float(fixed_usd) / len(buckets) if buckets else 0.0
    return scale, fixed_per


@dataclass
class PaygoTypeUsd:
    """Console Text-type Spend breakdown (from Usage explorer Type legend)."""

    cached: float = 0.0  # Cached prompt text tokens $
    input: float = 0.0  # Uncached prompt text tokens $
    output: float = 0.0  # Completion text tokens $
    reasoning: float = 0.0  # Reasoning text tokens $

    @property
    def total(self) -> float:
        return float(self.cached) + float(self.input) + float(self.output) + float(self.reasoning)

    def as_dict(self) -> dict[str, float]:
        return {
            "cached_usd": self.cached,
            "input_usd": self.input,
            "output_usd": self.output,
            "reasoning_usd": self.reasoning,
            "total_usd": self.total,
        }


def allocate_paygo(
    buckets: list[UsageBucket],
    *,
    paygo_usd: float,
    weight: str = "ticks",
    rates: TokenRates | None = None,
) -> dict[str, float]:
    """Allocate a known console/paygo cash total across buckets (single pool).

    weight:
      - ticks: costUsdTicks (default; matches internal metering intensity)
      - api: pure-API modeled $ share (uses rates if provided)
      - tokens: total token share

    Returns map key -> allocated USD. Sum equals paygo_usd (within float noise).
    Prefer allocate_paygo_by_type when console Type $ breakdown is available.
    """
    if paygo_usd < 0 or not buckets:
        return {}

    weights: dict[str, float] = {}
    for b in buckets:
        if weight == "api":
            w = float(b.api_est(rates))
        elif weight == "tokens":
            w = float(b.total)
        else:  # ticks
            w = float(b.ticks) if b.ticks > 0 else float(b.total)
        weights[b.key] = max(w, 0.0)

    total_w = sum(weights.values())
    if total_w <= 0:
        # equal split fallback
        share = float(paygo_usd) / len(buckets)
        return {b.key: share for b in buckets}

    return {k: float(paygo_usd) * (w / total_w) for k, w in weights.items()}


def allocate_paygo_by_type(
    buckets: list[UsageBucket],
    types: PaygoTypeUsd,
) -> tuple[dict[str, float], dict[str, dict[str, float]]]:
    """Allocate console Type-level $ by each bucket's share of that token type.

    Example (console Text legend for window):
      cached $3.28, prompt $1.76, completion $0.25, reasoning $0.05

    bill$[app] = sum over types of (app.tokens_type / total.tokens_type) * console_usd_type

    Returns (bill_by_key, detail_by_key) where detail has cached/input/output/reasoning $.
    Sum of bill_by_key equals types.total (within float noise).
    """
    if not buckets or types.total <= 0:
        return {}, {}

    sum_cached = sum(b.cached for b in buckets)
    sum_in = sum(b.uncached_in for b in buckets)
    sum_out = sum(b.output for b in buckets)
    sum_reason = sum(b.reasoning for b in buckets)

    bill: dict[str, float] = {}
    detail: dict[str, dict[str, float]] = {}

    for b in buckets:
        c = (b.cached / sum_cached * types.cached) if sum_cached > 0 and types.cached else 0.0
        i = (b.uncached_in / sum_in * types.input) if sum_in > 0 and types.input else 0.0
        o = (b.output / sum_out * types.output) if sum_out > 0 and types.output else 0.0
        r = (
            (b.reasoning / sum_reason * types.reasoning)
            if sum_reason > 0 and types.reasoning
            else 0.0
        )
        # If a type pool has $ but zero local tokens of that type, that pool is unallocated
        # (left on the floor) — rare; prefer keeping sum ≈ types.total via only positive bases.
        detail[b.key] = {
            "cached_usd": c,
            "input_usd": i,
            "output_usd": o,
            "reasoning_usd": r,
        }
        bill[b.key] = c + i + o + r

    return bill, detail


def list_price_usd(ticks: int) -> float:
    """Convert Build/API ``costUsdTicks`` to USD (1 USD = 10^10 ticks)."""
    return float(ticks) / float(TICKS_PER_USD)


def completion_tokens(
    *,
    output: int,
    reasoning: int,
    total: int = 0,
    input_tokens: int = 0,
) -> int:
    """Tokens billed at the output rate.

    Build logs ``outputTokens`` as completion+reasoning (input+output == total).
    Only add reasoning when the totals say it is extra.
    """
    out = max(int(output), 0)
    reason = max(int(reasoning), 0)
    if int(total) > 0 and abs(int(total) - (int(input_tokens) + out)) <= 1:
        return out
    return out + reason


def rates_for_prompt(rates: TokenRates, prompt_tokens: int) -> TokenRates:
    """2× list rates when the prompt reaches the published 200k long-context tier."""
    if int(prompt_tokens) < LONG_CONTEXT_PROMPT_TOKENS:
        return rates
    return TokenRates(
        uncached_input=rates.uncached_input * 2.0,
        cached_input=rates.cached_input * 2.0,
        output=rates.output * 2.0,
        label=f"{rates.label or 'rates'} ≥200k",
    )


def turn_list_usd(
    r: UsageRec | object,
    rates: TokenRates | None = None,
    *,
    prefer_ticks: bool = True,
) -> float:
    """list$ for one turn: ticks/1e10 (matches /usage Cost) or reconstructed rates."""
    ticks = int(getattr(r, "ticks", 0) or 0)
    if prefer_ticks and ticks > 0:
        return list_price_usd(ticks)
    cached = int(getattr(r, "cached", 0) or 0)
    inn = int(getattr(r, "input", 0) or 0)
    output = int(getattr(r, "output", 0) or 0)
    reasoning = int(getattr(r, "reasoning", 0) or 0)
    total = int(getattr(r, "total", 0) or 0)
    model = getattr(r, "model", None)
    base = rates or rates_for_model(str(model) if model else None)
    # Long-context 2× is already inside costUsdTicks. Do not apply it to
    # turn-aggregate input (a 1M-token turn may be many <200k calls).
    out_n = completion_tokens(output=output, reasoning=reasoning, total=total, input_tokens=inn)
    return api_estimate_usd(
        cached=cached,
        uncached_in=max(inn - cached, 0),
        output=out_n,
        reasoning=0,
        rates=base,
        reason_as_output=False,
    )


def parse_iso_date(s: str) -> date:
    return date.fromisoformat(s.strip()[:10])
