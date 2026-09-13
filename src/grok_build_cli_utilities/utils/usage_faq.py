"""Usage cost FAQ / caveats text (kept out of pricing.py)."""

# Plain multi-line footer (print with markup=False — [brackets] are not Rich tags).
COST_CAVEATS_SHORT = """\
list$ = estimated $ at public API prices × your local tokens.
est$  = path/regime spend lens (API ≈ list$; SuperGrok/Heavy pool ≈ 0; overage ≈ 1.9× list$).
Extra Credits $, weekly %, resets, and SuperGrok vs Heavy come from billing lines in logs/unified.jsonl.
Build Session Cost / Credits / Weekly limit are different meters — they will not match list$/est$.
FAQ: grok-utils usage info   ·   Tune: path scales or --cash-scale / --topoff-discount"""

COST_CAVEATS_LONG = """
FAQ — Why numbers do not match Grok Build /usage
------------------------------------------------
Grok Build and grok-utils show different *kinds* of money and tokens. None is
"wrong"; they answer different questions.

  Q: What is list$?
  A: Offline "as if API list rates" dollar total for the filtered turns:
       list$ = Build costUsdTicks ÷ 10^10 when the session log has ticks
               (same dollar as /usage Session Cost). If ticks are missing,
               tokens × published rates for --rates-model (default grok-4.6).
               Pass -m MODEL to force the rate table and ignore ticks.
     Data source: turn usage under ~/.grok/sessions (costUsdTicks + tokens).
     Not the SuperGrok wallet and not the X console.
     Cache% in the table (and why it matters for list$):
       Build reuses prompt/context tokens already paid for → those count as
       *cached* input, billed at the lower cached rate (e.g. $0.50/1M vs
       $2.00/1M uncached on grok-4.6; grok-4.5 cached is $0.30/1M). High cache%
       usually means *lower* list$ for the same total tokens — that is expected
       efficiency, not a bug.
     Formula sketch (rate-table fallback / -m):
       list$ = cached/1e6×cached_rate + uncached_in/1e6×input_rate
             + completion/1e6×output_rate
       (reasoning is usually already inside outputTokens; not added twice)
     Official ticks: cost_usd = costUsdTicks / 10_000_000_000

  Q: What is est$?
  A: Best-effort *spend lens* on top of list$ (not a second token meter):
       est$ = list$ × path/regime scale.
       API path              → scale 1.0 (est$ ≈ list$)
       SuperGrok / Heavy pool    → weekly limit < ~100% → Extra Credits idle → ~0
       SuperGrok / Heavy overage → weekly ~100% → Extra Credits burn → ~1.9× list$
       before first in-pool sample (≤7d) → pool ~0 (truncated billing log)
       weekly % unknown          → scale 1.0 + caveat (do not invent pool/overage)
     Optional override: --cash-scale or [usage] cash_scale (legacy single blend).

  Q: Why does Build Session Cost differ from list$ on the same work?
  A: Default list$ *is* Session Cost: costUsdTicks ÷ 10^10, same unit as /usage.
     They still diverge when:
       · /usage is "since start or last resume" and grok-utils is a --from/--to
         window (or several sessions rolled into one app row)
       · you took /usage mid-turn (in-progress tokens not yet in turn_completed)
       · you passed -m and forced a reconstructed rate table
     est$ is still a SuperGrok/Heavy spend lens (pool ≈ 0, overage ≈ 1.9×) — not
     Session Cost.

  Q: What are Credits, Weekly limit 100%, Auto topup $20 — do they change list$/est$?
  A: Those are *account-wide SuperGrok / Heavy wallet* meters (Build UI), not per-app:
       Extra Credits / Credits = prepaid balance still available
       Weekly limit            = included SuperGrok or Heavy pool (100% = exhausted)
       Auto topup              = e.g. $20 face charged to *refill* Extra Credits
                                 (not "this app cost $20")
     How they affect grok-utils output:
       • list$  — NOT affected. Always tokens × API list rates.
       • Credits $ / Auto topup amount — NOT plugged into the cost formula.
         Shown only as a *snapshot* (footer / auth status) so you can see what
         the wallet looks like. We do not auto-subtract top-ups from list$/est$.
       • Weekly % — only switch for session *est$* regime (pool ≈ 0 vs
         overage ≈ 1.9×). It does not change list$ or the Share bars.
     Offline snapshot source: logs/unified.jsonl billing lines
     (prepaidBalance, creditUsagePercent, currentPeriod.end, subscriptionTier)
     via auth status / cost footer.

  Q: What does "Wallet / auth  Extra Credits $… · weekly …% · Heavy session"
     plus a "Weekly Heavy pool resets  August 27, 19:08" line mean?
  A: Account snapshot for this machine right now — not per app and not the
     table math:
       Extra Credits $  — prepaid SuperGrok/Heavy balance left (billing log)
       weekly N%        — SuperGrok or Heavy weekly pool used so far this period
                          (only switches *est$* pool vs overage;
                          does not change list$ or Share bars)
       Weekly … pool resets — own line; included weekly pool (not Extra Credits)
                          refills at currentPeriod.end (same clock as Build
                          /usage "Resets"; not wrapped with the wallet row)
       SuperGrok / Heavy / API — login path + plan from billing
                          subscriptionTier (not from /usage turn files)
     Does not subtract Credits from list$/est$. Does not mean "this app spent
     $21.40". Same fields as: grok-utils auth status
     (source: logs/unified.jsonl billing fetch, best-effort / can be stale).
     The Build /usage panel may still title the week "SuperGrok" after you
     upgrade; the log field is the plan we use.

  Q: SuperGrok session vs API key — why did the X console miss my
     account / Extra Credits burn?
  A: Two different billing systems. If ~/.grok/auth.json has a SuperGrok
     login session, Build prefers that path (cached_token) even when
     XAI_API_KEY is set. Token use and auto top-ups then hit the SuperGrok
     wallet (weekly pool + Extra Credits), not the API-key prepaid/paygo
     ledger shown under X console "API key Usage". So the console can look
     quiet while SuperGrok Credits still move. Check: grok-utils auth status
     Force API: [auth] preferred_method = "api_key" in config.toml, or remove
     auth.json (recreated on grok login). Auth history is best-effort process-
     level timeline from logs — not per-turn billing. Pre-log gaps are labeled
     unknown.  grok-utils auth status --history

  Q: Pack promos (−20% / −25% / −40%) and plan-advisor?
  A: usage cost -P ranks Pure API, SuperGrok, Heavy, and offered pack promos
     (−20/−25/−40 tops) from this window's list$ run-rate — no flag required.
     ★ marks the single cheapest option for the window (tops priced @ list$ face).
     Current SuperGrok vs Heavy is read from billing log subscriptionTier
     (same lines as Extra Credits / weekly %). Footer marks the current plan
     and labels the other rows as what-if. A window that spans an upgrade
     notes the blend. Session /usage turns do not carry the plan.
     Optional: --topoff-discount 0.40 pins your promo for est_cash$.
     Caveats Interactive users should know:
       · weekly include $ is estimated — Heavy Build often exhausts SuperGrok early
       · Extra Credits may burn faster than pure list$ — advisor shows a sensitivity
         line at overage scale (~1.9×) so Heavy can win if burn stays high
       · monthly spend can be burstier than the smooth average (auto top-ups)
       · promos temporary; quieter months favor Pure API
     Config: topoff_discount_scenarios = [0.20, 0.25, 0.40]

  Q: Which number should I trust for budgeting?
  A: - Per-app / per-day activity → list$
     - Extra-credit burn estimate → est$ (regime-aware)
     - "How expensive was this chat session?" → Build Session Cost
     - "How much is left / weekly pool?" → Extra Credits $ + weekly % (auth status)
     - "Which plan if I keep this pace?" → usage cost --plan-advisor (-P)

  Q: Why does the cost table show only 10 rows?
  A: Default is top 10 by list$. --all prints every row.
     TOTALS is the whole window even when the table is truncated.
     Truncated tables say --all to see all.

  Q: Why is --from a local date?
  A: A YYYY-MM-DD with no time is a day on the machine in front of you.
     Weekly pool resets already print in local time to match Build /usage.
     --from / --to use that same clock, so work at 11:51 PM stays on that
     local day. UTC used to put 11:51 PM ET on the next UTC day, which
     looked like a missing session. It was a timezone cut.
     --tz UTC restores the old UTC calendar. --tz America/New_York (IANA)
     or [usage] date_tz in grok-utils.toml pins a zone. CLI --tz wins.
     Default is local when neither is set.

  Q: What is --by app vs --by pr vs --by session?
  A: --by app is the repo inferred from cwd. Parent clones, repo-issue-N
     folders, and Grok worktrees for that repo are one row (prompts/list$
     summed). Grouping is case-insensitive. Display prefers the GitHub/
     folder spelling. #N is not used on --by app.
     --by pr lists every created issue/PR across repos (native creates only).
     --by session is one row per Grok Build chat. Unlabeled session Keys
     still pretty-print repo-issue-N clones as repo#N so chats stay distinct.

  Q: Why is --by session or --by pr still the folder name?
  A: PR-level Keys and clean session labels appear only when the Grok Build
     session reports them. If you skip this, you still get --by app (the
     repo inferred from cwd).
       · One Grok Build session per unit of work. Several PRs from one parent
         chat stay one unsplit --by pr row. Keys with several PRs are one
         session; tokens are not split.
       · Session cwd is the repo (or Grok worktree / repo-issue-N clone) for
         that work. Not an unrelated folder. --by app is the repo inferred
         from cwd. Issue worktree folders roll into the repo Key. A chat
         started in the wrong repo shows that folder's name. PR labels, if
         any, come from whatever create_pull_request or gh pr create ran.
       · PR labels: only github create_pull_request OkayOutput (number,
         html_url) or gh pr create stdout URL in updates.jsonl. Chat text
         and get_pull_request do not count.
       · Fixes or Closes in the create body puts the issue number in the Key.

  Q: Common commands (novice)
  A:  grok-utils usage cost --from 2026-08-01 --by app -m grok-4.6
      grok-utils usage cost --from 2026-08-01 --by app --all
      grok-utils usage cost --from 2026-08-01 --by session
      grok-utils usage cost --from 2026-08-01 --by pr
      grok-utils usage cost --from 2026-08-01 --by app -m grok-4.6 -P
      grok-utils usage report --by app --from 2026-08-01
      # --tokens is only needed when not grouping by app, e.g.:
      # grok-utils usage report --by day --tokens --from 2026-08-01
      grok-utils auth status
      grok-utils usage cost ... -P --topoff-discount 0.25

CAVEATS & COST LEDGERS (technical)
----------------------------------
Where list$/tokens come from (local only — no network):
  Each completed Build turn writes usage into that session's updates.jsonl
  under ~/.grok/sessions/...  Event: turn_completed.usage.
  Why this matters: grok-utils never sees your live X console or SuperGrok
  card charges; it reconstructs activity from these on-disk turn records.

  Fields we use (what / why):
    inputTokens       — total prompt/context tokens for the turn (basis for
                        input $; split into cached vs uncached below)
    cachedReadTokens  — portion of input served from cache (cheaper list rate;
                        drives Cache% and lowers list$ for the same size turns)
    outputTokens      — model reply tokens (higher list rate than input)
    reasoningTokens   — "thinking" tokens when the model emits them; we price
                        them like output (same $/1M) because list tables do
    costUsdTicks      — actual billed $ × 10^10 (xAI cost tracking). Default
                        list$ is ticks/1e10 — same meter as /usage Session Cost.
    modelCalls        — how many model invocations the turn made (diagnostics)

  Dedup by prompt_id: if the same prompt is logged more than once (retries,
  partial writes), we keep the row with the largest totalTokens so one user
  message is not double-counted in list$/est$.

list$ formula:
  If costUsdTicks present (default): ticks / 10^10   (= /usage Session Cost)
  Else or with -m: cached/1e6 × cached_rate + uncached_in/1e6 × input_rate
                   + completion/1e6 × output_rate
  where uncached_in ≈ max(0, input − cached)
  Long-context 2× is already inside costUsdTicks; -m reconstruction uses the
  standard (≤200k) published rates only.

est$ = list$ × cash_scale (path/regime or forced)
  Built-in path defaults (unless forced):
    cash_scale_api = 1.0
    cash_scale_supergrok_pool = 0.0
    cash_scale_supergrok_overage = 1.9
  Force one number for a window:
    --cash-scale N
    --prepaid-usd + --credits-remaining  (scale = wallet burn / list$)
    [usage] cash_scale = 0.69   # optional legacy blend; disables path split

  Top-off promo (card, not list$):
    --topoff-discount 0..1   or  [usage] topoff_discount
    est_cash$ = est$ × (1 − discount) when discount > 0
    plan-advisor scenarios: topoff_discount_scenarios = [0.20, 0.25, 0.40]

Effective rates (list × scale) assume a *uniform* scale vs list when forced.
  Prepaid may not discount cached/input/output equally — only wallet total is known offline.

--plan-advisor / -P
  Compare pure API vs SuperGrok vs SuperGrok Heavy for the same window
  (run-rate → monthly projection). "Best fit" assumes this window's intensity
  continues. Table ranks full-price plans plus offered pack promos (−20/−25/−40).
  Weekly pool $ sizes are estimates. Current plan (SuperGrok vs Heavy) comes
  from billing log ctx.subscriptionTier — not from session /usage turns.
  Planner footer marks the current plan; the other subscription row is a what-if.

  [usage]
  supergrok_usd = 30
  heavy_usd = 300
  supergrok_weekly_include_usd = 35
  heavy_weekly_include_usd = 150
  project_days = 30
  topoff_discount = 0.0
  topoff_discount_scenarios = [0.20, 0.25, 0.40]

MAINTAINING DEFAULTS (Phase 1 — no network in usage cost)
  When xAI announces API rate or SuperGrok/Heavy price changes:
    1. Update rate tables / plan constants in utils/pricing.py
    2. Bump PRICES_LAST_VERIFIED (ISO date)
    3. Or set overrides in ~/.grok/grok-utils.toml without a release
  Do not auto-scrape x.ai or call APIs from day-to-day cost reports (v1).

  Future (optional, opt-in): refresh list rates from Models API with a key:
    GET https://api.x.ai/v1/models  or  .../models/{model_id}
    Fields: prompt_text_token_price, cached_prompt_text_token_price,
            completion_text_token_price (+ long-context variants)
    Units: USD cents per 100M tokens → divide by 100 for $ per 1M.
  That updates list$ tables only — not subscription fees or weekly pool sizes
  (those still come from x.ai pricing announcements / human check).

--rates-model / -m  forces a reconstructed rate table (ignores ticks).
  Omit -m to use costUsdTicks (matches /usage). Default fallback table: grok-4.6.
  Reconstruction uses standard ≤200k rates; long-context 2× lives in ticks.

Session UI Cost is lifetime of a session (may span SuperGrok + API eras).
Weekly limit / credits / auto-topup are account-global, not per-app.
""".strip()
