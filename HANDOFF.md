# HANDOFF — aider-ll project

## Mission
Create a slim version of aider by making the heavy runtime dependencies **optional** (feature flags / granular extras). Default `pip install aider-chat` = lite (~96M); `pip install aider-chat[all]` = full (everything). Core chat/edit/commit/`!`/`/run` must remain fully functional. litellm stays in core (out of scope).

## Current state (as of this handoff)
- Branch: `aider-ll`, clean tree, HEAD == `upstream/main` == `5dc9490bb` (2026-05-22). **Upstream development has basically stopped** (~3 months quiet) → near-zero merge-conflict risk; effectively a standalone project.
- `.venv` exists with the 107 runtime deps (≈ "full" mode) but **no pytest**.
- Repo layout: flat, package = `aider/`, `pyproject.toml` build config.

## The plan — pilot-first, feature flags
1. Framework (additive, safe): optional-import helper → lite/full test infra + baseline → granular extras + `[all]`
2. Pilot ONE feature end-to-end (voice) → learn → replicate for the rest

## Verified code facts (do NOT re-verify, trust these)
- **Importers (single core importer per feature):** repomap→base_coder.py:47; linter→base_coder.py:37; analytics→main.py:22+base_coder.py:32; voice→commands.py:16; watch→main.py:38; scrape→commands.py:24 (+gui.py:14, already lazy via main.py:236); copypaste→main.py:27.
- **Construction pattern:** on-demand (constructed only when active): RepoMap (base_coder:497, gated by `use_repo_map && map_tokens>0`), FileWatcher (main:1028, `--watch-files`), Voice (commands:1260, `/voice`), Scrape (`/web`). Always-on (constructed unconditionally): Linter (base_coder:526), Analytics (base_coder:343), ClipboardWatcher (main:1040).
- **Heavy imports per feature module:** repomap.py (tree_sitter, grep_ast, diskcache, networkx), linter.py (grep_ast), analytics.py (posthog, mixpanel), voice.py (pydub), watch.py (grep_ast, watchfiles, pathspec), scrape.py (pypandoc), copypaste.py (pyperclip), commands.py (pyperclip, PIL), models.py (PIL).
- **Strategy A (on-demand features):** lazy-import the feature module at its single core site; feature module internals UNTOUCHED. Strategy A fits repomap, watch, voice, scrape.
- **Strategy B (always-on features):** guard deps inside the feature module so it imports cleanly without them. Strategy B fits linter, analytics, copypaste/images.
- `LazyLiteLLM.__getattr__` precedent in `aider/llm.py` (in-repo idiom for deferred heavy imports).

## Decisions locked
- **Extras packaging:** inline `[project.optional-dependencies]` in pyproject.toml (not .in/.txt files).
- **`[all]`** includes everything incl. playwright (matches current behavior).
- **Voice degrade:** show clear warning (`voice not installed; pip install aider-chat[voice]`).
- **Linter in lite:** drop tree-sitter + flake8 → degrade to **compile-only** (bare `compile()` syntax check, no "Error running flake8" noise).
- **litellm→openai swap: DEFERRED/out of scope.**
- **tiktoken approximation** for token counting is fine (future openai path).
- **cost = 0** for any openai-path cost calc (future).

## Commit sequence (verify-gated; each commit installable+runnable in BOTH lite and full modes; NEVER commit unverified)
1. `build: add optional-import helper` — `aider/optional.py` (new)
2. `build: add lite/full test infrastructure and baseline` — `scripts/smoke_test.sh`, test venvs, record green baseline
3. `build: add granular extras and all aggregate (inline)` — `pyproject.toml`
4. `feat: make voice deps optional` — **PILOT** — commands.py:16 lazy + `/voice` warning; `voice` extra; `importorskip` test_voice (see trap); verify both modes
5. `feat: make analytics deps optional` — analytics.py guard (file-log only)
6. `feat: make repomap deps optional` — base_coder.py lazy RepoMap, warn when enabled-but-missing
7. `feat: make tree-sitter lint deps optional` — linter.py → compile-only in lite
8. `feat: make watch deps optional` — main.py lazy FileWatcher
9. `feat: make scrape/browser deps optional` — commands.py lazy scrape; pypandoc/bs4 → extra
10. `feat: make clipboard/image deps optional` — copypaste.py/commands.py/models.py guards (pyperclip/PIL)
11. `docs: document extras and slim install` — README

## Extras map (inline, granular)
- `repomap`: grep-ast, tree-sitter-language-pack, networkx, scipy, numpy, diskcache
- `lint`: grep-ast, tree-sitter stack, flake8, pyflakes, pycodestyle, mccabe
- `voice`: pydub, sounddevice, soundfile, numpy, scipy
- `browser`: streamlit, pypandoc, beautifulsoup4
- `playwright`: playwright (already exists)
- `analytics`: posthog, mixpanel
- `watch`: watchfiles
- `clipboard`/`images`: pyperclip, pillow
- `all`: union of all above

## Verification protocol
- **lite venv:** core deps + pytest; core test subset + feature tests that self-skip.
- **full venv:** core + `[all]` + pytest; full suite.
- **Smoke (lite):** `import aider`, `aider --exit`, `!echo hi`, `--message` vs a mock OpenAI-compatible endpoint.
- Hard rule: **verify both modes before every commit.**
- Note: voice/browser tests need hardware/playwright — can't fully run in sandbox; use importorskip.

## Traps for future self
- `test_voice.py:5` imports `numpy` at module top → `importorskip("pydub")`/`("numpy")` must be placed BEFORE it (reorder `import pytest` up).
- `test_repomap.py:13`, `test_watch.py:5`, `test_linter.py:6` import the aider feature module at top → rely on the aider-module guard + `importorskip` for the heavy dep.
- `test_scrape.py` imports `Scraper` + `Commands` → needs the commands.py lazy fix.
- Startup chain: base_coder imports repomap/linter/analytics at TOP LEVEL — these are the critical ones to make lazy, else lite install fails at import.
- RepoMap is ON by default (map_tokens=1024) → lite launches would warn; consider silent-on-default, warn-on-explicit.
- Ordering invariant: guards must precede dep-stripping per feature.

## Deferred
- litellm→openai facade (Phase B): separate `aider/llm_backend/` with `openai.py` + `litellm.py` + facade in `aider/llm.py`; cost=0; tiktoken approx. NOT now.
- Optional `aider-ll` console-script alias.

## First actions when resuming
1. Install pytest into `.venv` (full mode) + create lite venv (core deps).
2. Run full suite → record green baseline.
3. Implement framework commit 1, then voice pilot, verifying each step.
