---
title: grok-utils
---

<script>
  // Activate landing mode and configure Tailwind to match arsenal style
  document.documentElement.classList.add('grok-landing-active');
  
  // Tailwind play CDN config (runs after script loads)
  function initTailwind() {
    if (window.tailwind) {
      window.tailwind.config = {
        theme: {
          extend: {
            fontFamily: {
              'display': ['Space Grotesk', 'Inter', 'system-ui', 'sans-serif']
            }
          }
        }
      };
    }
  }
  // Run soon after load
  setTimeout(initTailwind, 300);
  window.addEventListener('load', initTailwind);
</script>

<div class="grok-landing">
<style>
  /* Early hide of Material top chrome to prevent flash of default banner */
  body .md-header,
  body .md-sidebar,
  body .md-tabs,
  body .md-footer,
  body .md-announce {
    display: none !important;
  }
  /* Zero out wrappers immediately so custom top nav is flush at viewport top */
  html, body,
  body .md-main,
  body .md-main__inner,
  body .md-content,
  body .md-content__inner,
  body article.md-typeset {
    margin: 0 !important;
    padding: 0 !important;
    padding-top: 0 !important;
    max-width: 100% !important;
    width: 100% !important;
  }
  body .md-grid {
    max-width: 100% !important;
    margin: 0 !important;
    padding: 0 !important;
  }
</style>

<!-- Custom Arsenal-style Navbar -->
<nav class="grok-nav border-b border-zinc-800 bg-zinc-950/90 backdrop-blur-lg sticky top-0 z-50">
  <div class="max-w-screen-xl mx-auto px-6 py-4 flex items-center justify-between">
    <div class="flex items-center gap-x-3">
      <div class="w-9 h-9 bg-white rounded-xl flex items-center justify-center">
        <span class="text-zinc-950 font-bold text-2xl tracking-tighter">G</span>
      </div>
      <div>
        <span class="font-display text-2xl font-semibold tracking-tighter text-white">grok-utils</span>
        <span class="text-xs text-zinc-500 ml-1 align-super">by Cobus Greyling</span>
      </div>
    </div>
    
    <div class="flex items-center gap-x-6 text-sm">
      <a href="#utilities" class="text-zinc-400 hover:text-white transition-colors">Utilities</a>
      <a href="#showcases" class="text-zinc-400 hover:text-white transition-colors">Showcases</a>
      <a href="#get-started" class="text-zinc-400 hover:text-white transition-colors">Get Started</a>
      <a href="https://github.com/cobusgreyling/grok-build-cli-utilities" target="_blank" 
         class="flex items-center gap-x-2 px-4 py-2 rounded-xl bg-white text-zinc-950 text-sm font-medium hover:bg-zinc-100 transition-all"
         aria-label="">
        <i class="fab fa-github"></i>
        <span>GitHub</span>
      </a>
    </div>
  </div>
</nav>

<!-- Hero -->
<div class="hero-bg border-b border-zinc-800" style="background: linear-gradient(180deg, #0a0a0a 0%, #111111 100%);">
  <div class="max-w-screen-xl mx-auto px-6 pt-16 pb-8">
    <div class="flex flex-col lg:flex-row gap-8 items-start">
      <!-- Left: text content -->
      <div class="lg:w-3/5">
        <div class="inline-flex items-center gap-x-2 px-4 py-1.5 rounded-2xl bg-zinc-900 border border-zinc-800 mb-6">
          <div class="w-2 h-2 bg-emerald-400 rounded-full animate-pulse"></div>
          <span class="text-sm font-medium tracking-tight text-zinc-300">Power tools for <span class="font-semibold text-white">Grok Build</span></span>
        </div>
        
        <h1 class="font-display text-6xl md:text-7xl leading-[0.95] tracking-tighter font-semibold mb-4 text-white">
          The definitive<br>CLI toolkit for<br>Grok Build
        </h1>
        
        <p class="text-2xl text-zinc-400 max-w-lg tracking-tight mb-8">
          12+ production-grade utilities.<br>
          Sessions, skills, backups, analytics, MCP, plugins &amp; hooks.<br>
          <span class="text-emerald-400 text-lg">Beautiful • Safe-by-default • Scriptable with --json</span>
        </p>
        
        <div class="flex flex-wrap items-center gap-x-4 gap-y-3">
         
          
          <a href="#get-started" 
             class="grok-btn-secondary">
            Get started
          </a>
          
          <a href="#utilities" 
             class="grok-btn-secondary">
            Explore utilities
          </a>
        </div>
        
        <div class="mt-8 flex items-center gap-x-4 text-sm text-zinc-500">
          <div class="flex -space-x-1">
            <div class="w-6 h-6 bg-zinc-800 border border-zinc-700 rounded-full"></div>
          </div>
          <span><strong class="text-zinc-400">Sole author &amp; maintainer:</strong> Cobus Greyling</span>
        </div>
      </div>

      <!-- Right: promo card to fill space and balance layout -->
      <div class="lg:w-2/5 w-full">
        <div class="bg-white text-zinc-950 rounded-2xl p-5 shadow-2xl">
          <div class="flex items-center gap-4">
            <div class="flex-shrink-0">
              <div class="w-14 h-14 bg-[#238636] rounded-xl flex items-center justify-center">
                <i class="fab fa-github text-white text-4xl"></i>
              </div>
            </div>
            <div class="min-w-0 flex-1">
              <div class="font-semibold text-lg">View on GitHub</div>
              <div class="text-xs text-zinc-500">Star the repo • See the code • Contribute</div>
              <a href="https://github.com/cobusgreyling/grok-build-cli-utilities" 
                 class="inline-block mt-2 text-sm font-medium text-blue-600 hover:underline">
                github.com/cobusgreyling/grok-build-cli-utilities →
              </a>
            </div>
          </div>
        </div>
      </div>
    </div>
  </div>

  <!-- Hero banner / visual (matching arsenal style) -->
  <div class="max-w-screen-xl mx-auto px-6 pt-8 pb-4">
    <img src="assets/header.jpg" alt="Grok Build CLI Utilities banner" 
         class="w-full rounded-2xl border border-zinc-800 shadow-2xl"
         style="max-height: 380px; object-fit: cover; display: block;">
  </div>
</div>

<!-- Stats -->
<div class="max-w-screen-xl mx-auto px-6 pt-12 pb-8">
  <div class="grid grid-cols-2 md:grid-cols-4 gap-6">
    <div>
      <div class="stat-number text-white">12+</div>
      <div class="text-sm text-zinc-400 mt-1 tracking-tight">Power commands &amp; subcommands</div>
    </div>
    <div>
      <div class="stat-number text-white">7</div>
      <div class="text-sm text-zinc-400 mt-1 tracking-tight">Core utility groups</div>
    </div>
    <div>
      <div class="stat-number text-emerald-400">100%</div>
      <div class="text-sm text-zinc-400 mt-1 tracking-tight">Safe-by-default (dry-run)</div>
    </div>
    <div>
      <div class="stat-number text-white">--json</div>
      <div class="text-sm text-zinc-400 mt-1 tracking-tight">Scriptable on every command</div>
    </div>
  </div>
</div>

<!-- Intro -->
<div class="max-w-screen-xl mx-auto px-6 py-10 border-t border-zinc-800">
  <div class="max-w-2xl">
    <h2 class="section-header text-white">See what grok-utils can actually do.</h2>
    <p class="text-xl text-zinc-400 tracking-tight">
      Most CLI tools are toys or thin wrappers. grok-utils ships real, daily-driver power tools that operate directly on your <code>~/.grok</code> data — with beautiful output, ironclad safety defaults, and first-class JSON support for scripting and dashboards.
    </p>
    <p class="mt-4 text-zinc-400">
      Everything here was built to make you dramatically more productive with Grok Build. Zero mocks. Real data only.
    </p>
  </div>
</div>

<!-- The Utilities -->
<div id="utilities" class="max-w-screen-xl mx-auto px-6 py-8">
  <div class="flex gap-8">
    <!-- Left content: header + grid -->
    <div class="flex-1">
      <div class="flex items-end justify-between mb-6">
        <div>
          <span class="grok-tag">THE TOOLKIT</span>
          <h2 class="section-header text-white mt-1">The Utilities</h2>
        </div>
      </div>

      <div class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
        <!-- sessions -->
        <div class="grok-card">
          <div class="flex items-center justify-between mb-3">
            <div class="font-semibold text-lg text-white tracking-tight">sessions</div>
            <span class="grok-tag">Core</span>
          </div>
          <p class="text-sm text-zinc-400 mb-4">Advanced session browser, search (FTS), deep analysis, export (md/html/json), resume, and safe pruning.</p>
          <div class="grok-code text-xs text-emerald-300 mb-2">grok-utils sessions list --project acme --limit 20</div>
          <div class="grok-code text-xs text-emerald-300">grok-utils sessions analyze 019e87 --deep</div>
        </div>

        <!-- skills -->
        <div class="grok-card">
          <div class="flex items-center justify-between mb-3">
            <div class="font-semibold text-lg text-white tracking-tight">skills</div>
            <span class="grok-tag">Core</span>
          </div>
          <p class="text-sm text-zinc-400 mb-4">Full lifecycle: discover (priority-aware), create high-quality starters, validate, pack/unpack for sharing.</p>
          <div class="grok-code text-xs text-emerald-300 mb-2">grok-utils skills create deploy --desc "..."</div>
          <div class="grok-code text-xs text-emerald-300">grok-utils skills validate ./my-skill</div>
        </div>

        <!-- backup -->
        <div class="grok-card">
          <div class="flex items-center justify-between mb-3">
            <div class="font-semibold text-lg text-white tracking-tight">backup</div>
            <span class="grok-tag">Core</span>
          </div>
          <p class="text-sm text-zinc-400 mb-4">Industrial-strength backups with SHA-256 manifests. Selective sessions by project. Extremely safe restore (dry-run default).</p>
          <div class="grok-code text-xs text-emerald-300">grok-utils backup create --include-sessions</div>
        </div>

        <!-- usage -->
        <div class="grok-card">
          <div class="flex items-center justify-between mb-3">
            <div class="font-semibold text-lg text-white tracking-tight">usage</div>
            <span class="grok-tag">Analytics</span>
          </div>
          <p class="text-sm text-zinc-400 mb-4">Stunning reports, sparklines, timelines, model breakdowns + rough cost estimates. Group by project or model.</p>
          <div class="grok-code text-xs text-emerald-300 mb-2">grok-utils usage report --by project --top 8</div>
          <div class="grok-code text-xs text-emerald-300">grok-utils usage cost --by model</div>
        </div>

        <!-- mcp + worktree + others -->
        <div class="grok-card">
          <div class="flex items-center justify-between mb-3">
            <div class="font-semibold text-lg text-white tracking-tight">mcp</div>
            <span class="grok-tag">Ecosystem</span>
          </div>
          <p class="text-sm text-zinc-400 mb-4">Inspect config, doctor PATH checks, test servers, and easy example injection for filesystem, GitHub, SQLite etc.</p>
          <div class="grok-code text-xs text-emerald-300">grok-utils mcp doctor</div>
        </div>

        <div class="grok-card">
          <div class="flex items-center justify-between mb-3">
            <div class="font-semibold text-lg text-white tracking-tight">worktree + memory</div>
            <span class="grok-tag">Hygiene</span>
          </div>
          <p class="text-sm text-zinc-400 mb-4">Correlate git worktrees with sessions (find zombies). Cross-session memory explorer and search.</p>
          <div class="grok-code text-xs text-emerald-300">grok-utils worktree prune-orphaned --dry-run</div>
        </div>
      </div>

      <div class="mt-4 text-sm text-zinc-500">
        Plus <strong class="text-zinc-400">plugins</strong>, <strong class="text-zinc-400">hooks</strong>, <strong class="text-zinc-400">config</strong>, <strong class="text-zinc-400">logs</strong>, and the excellent <strong class="text-white">doctor</strong> health check.
        <a href="commands/" class="text-emerald-400 hover:underline ml-1">See every command →</a>
      </div>
    </div>

    <!-- Right: vertical label to fill space and match the design intent in screenshots -->
    <div class="hidden xl:flex flex-col items-center justify-center text-blue-400" 
         style="writing-mode: vertical-rl; text-orientation: mixed; letter-spacing: 2px; font-size: 0.75rem; font-weight: 600; width: 32px;">
      FULL COMMAND REFERENCE
      <i class="fas fa-arrow-right text-xl mt-4" style="writing-mode: horizontal-tb; transform: rotate(90deg);"></i>
    </div>
  </div>
</div>

<!-- Real work / Showcases -->
<div id="showcases" class="max-w-screen-xl mx-auto px-6 py-12 border-t border-zinc-800">
  <div class="mb-6">
    <span class="grok-tag">NOT THEORY</span>
    <h2 class="section-header text-white mt-1">Real work. Real productivity.</h2>
    <p class="text-lg text-zinc-400 max-w-xl">These tools operate directly against your live <code>~/.grok</code> data with rich terminal output and zero configuration.</p>
  </div>

  <div class="grid grid-cols-1 lg:grid-cols-2 gap-4">
    <div class="grok-card">
      <div class="grok-tag-flagship mb-3 inline-block">FLAGHIP</div>
      <h3 class="text-xl font-semibold text-white tracking-tight mb-2">Session forensics &amp; export</h3>
      <p class="text-zinc-400 text-sm mb-3">List, search (leveraging Grok's own FTS), deep analyze with signals + rewinds, export beautiful markdown or self-contained HTML for reviews and handoff.</p>
      <div class="text-xs text-zinc-500">grok-utils sessions analyze 019e87 • grok-utils sessions export ... --format html</div>
    </div>

    <div class="grok-card">
      <div class="grok-tag-flagship mb-3 inline-block">DAILY DRIVER</div>
      <h3 class="text-xl font-semibold text-white tracking-tight mb-2">Usage + Cost awareness</h3>
      <p class="text-zinc-400 text-sm mb-3">Visual reports with unicode bars and sparklines. Model and project breakdowns. Rough cost estimates to spot expensive work early.</p>
      <div class="text-xs text-zinc-500">grok-utils usage report --by project • grok-utils usage cost --by model</div>
    </div>
  </div>
</div>

<!-- Get Started -->
<div id="get-started" class="max-w-screen-xl mx-auto px-6 py-12 border-t border-zinc-800 bg-zinc-950">
  <div class="max-w-2xl">
    <span class="grok-tag">30 SECONDS</span>
    <h2 class="section-header text-white mt-2">Get started</h2>

    <div class="grok-code mb-6 text-sm">
# Recommended (isolated)
pipx install grok-build-cli-utilities

# Or with pip
pip install grok-build-cli-utilities

grok-utils doctor
grok-utils --help
    </div>

    <div class="flex flex-wrap gap-3">
      <a href="installation/" class="grok-btn-primary text-sm">Installation docs</a>
      <a href="quickstart/" class="grok-btn-secondary text-sm">Quickstart &amp; examples</a>
      <a href="https://github.com/cobusgreyling/grok-build-cli-utilities" target="_blank" class="grok-btn-secondary text-sm">Source on GitHub</a>
    </div>

    <p class="text-xs text-zinc-500 mt-6">Works directly with your real <code>~/.grok</code>. Supports <code>--grok-home</code> / <code>GROK_HOME</code>. Every destructive action defaults to <code>--dry-run</code>.</p>
  </div>
</div>

<!-- Philosophy / Footer-like -->
<div class="max-w-screen-xl mx-auto px-6 py-10 text-sm text-zinc-400 border-t border-zinc-800">
  <div class="flex flex-col md:flex-row md:items-center gap-y-2 md:justify-between">
    <div>
      <strong class="text-zinc-300">Philosophy:</strong> Safe first. Beautiful &amp; fast. Scriptable. Real data only. Minimal deps.
    </div>
    <div class="text-xs">
      MIT © 2026 Cobus Greyling • 
      <a href="https://github.com/cobusgreyling/grok-build-cli-utilities" class="hover:text-white">GitHub</a> • 
      <a href="philosophy/" class="hover:text-white">More on the approach</a>
    </div>
  </div>
  <div class="text-[10px] text-zinc-600 mt-3">NOT AFFILIATED WITH xAI • BUILT TO MAKE GROK BUILD USERS DRAMATICALLY MORE PRODUCTIVE</div>
</div>

</div>

<!-- End of custom landing -->
