---
name: vue-component-analyzer
description: Analyze Vue 3 component structure in client/src and produce a ranked report of performance and code-reuse optimizations (oversized components, duplicated logic/markup that should become a composable or shared component, reactivity and rendering waste, v-for key problems, eager route loading, repeated fetching), then offer to apply fixes. Use this skill whenever the user asks to review, audit, analyze, refactor, clean up, speed up, or "optimize" Vue components, views, or the frontend, asks why a page is slow or re-renders, asks what could be extracted or reused, or mentions duplication across .vue files, even if they don't say "analyze". Prefer it over the generic /optimize command for anything frontend-specific.
---

# Vue Component Analyzer

Find the changes that will make this app's Vue components faster or less duplicated, explain each one with evidence, and let the user choose what to fix. The report matters more than the fixes. Someone should be able to read it and trust that every finding is real, sits at the stated line, and is worth the effort.

## Project context

- Vue 3 Composition API, Vite, vue-router 4, axios. Source is in `client/src/`: views in `views/`, shared components in `components/`, shared logic in `composables/` (`useFilters`, `useI18n`, `useAuth`), helpers in `utils/` (`currency.js`), and the HTTP client in `api.js`.
- Data flow: filters (`useFilters`) feed `api.js`, which calls FastAPI. Raw responses go in refs, derived data goes in computeds. Recommendations should keep this shape.
- CLAUDE.md rules a finding can cite: unique `v-for` keys (`sku`, `month`, etc., never `index`); validate dates before `.getMonth()`; no emojis in the UI; custom SVG charts and CSS Grid layouts; global styles and design tokens live in `App.vue`.
- CLAUDE.md requires any creation or significant change to a `.vue` file to go through the **vue-expert** subagent. That applies when applying fixes (see "Applying fixes").

## Workflow

### 1. Scope

Work out the target from the request: one file, a few files, a folder, or all of `client/src`. If the request is vague ("optimize the frontend"), analyze everything but spend the deep reading on the largest and most-used files. Big files are where most of the gains are.

### 2. Run the scanner for leads

```bash
python3 .claude/skills/vue-component-analyzer/scripts/scan_vue.py client/src            # whole app
python3 .claude/skills/vue-component-analyzer/scripts/scan_vue.py client/src/views/Orders.vue
```

It prints a per-file size table (template/script/style lines) and a list of leads with `file:line`: index or missing `v-for` keys, `v-if` and `v-for` on the same element, in-place `.sort()`/`.reverse()`, function calls in template interpolation, deep watchers, unpaired `addEventListener`, helpers that redefine something in `utils/` or `composables/`, function names defined in several files, API methods called from several views, and eagerly imported routes.

The scanner works from regexes, so treat its output as leads to check, not conclusions. Before reporting a lead, open the file and confirm it. For example, a `.sort()` on a freshly built array (`.filter(...).sort(...)`) is fine, and a function call in `{{ }}` that does trivial formatting is not worth reporting. Drop false positives without comment.

### 3. Read the code

The scanner can't see design-level issues, and those are often the most valuable. Read the target components and work through `references/checklist.md`. It lists what to look for under performance and reuse, how to judge severity, and the fix to recommend for each. Compare similar files side by side (for example, all the `*DetailModal.vue` files, or every view that fetches with filters). Duplication only shows up in comparison.

### 4. Write the report

Use this structure. Keep it skimmable: one short paragraph per finding, with evidence instead of adjectives.

```markdown
# Vue component analysis: <scope>

## Summary
<2-4 sentences: overall shape, the 1-3 changes with the best payoff, rough size of the opportunity>

## Findings

### 1. <imperative title, e.g. "Extract a shared BaseModal from 6 detail modals"> [High | Medium | Low] · <Performance | Reuse>
**Where:** `client/src/components/CostDetailModal.vue:12`, `.../BacklogDetailModal.vue:10`, ...
**What:** <what the code does now, with a short snippet if it helps>
**Why it matters:** <concrete consequence: extra renders, extra requests, N copies to keep in sync, a correctness risk>
**Suggested change:** <the specific refactor, with a short before/after snippet where useful>
**Effort:** <S | M | L>

### 2. ...

## Not worth changing
<optional: things that look suspicious but are fine, so the reader doesn't waste time on them>

## Next steps
<numbered list of findings the user can ask to have applied, highest payoff first>
```

Rank by payoff (impact against effort), not by file order. Severity guide:
- **High**: user-visible slowness, wasted network requests, a correctness bug hidden inside a perf pattern (in-place sort mutating source data, index keys on lists that reorder), or duplication across 3+ files.
- **Medium**: measurable but modest waste, duplication in 2 files, components large enough that changing them is risky.
- **Low**: micro-optimizations and tidy-ups. Group several Low items into one finding instead of listing each one.

Every finding needs a real `file:line`. If you can't point at a line, it isn't a finding yet. If the report runs past about 12 findings, keep the best ones and summarize the rest in one line. A long list buries the important items.

If the user asked for the report to be saved, write it to the path they gave. Otherwise show it in the conversation.

### 5. Offer fixes

End by asking which findings to apply (for example, "Want me to apply 1, 2 and 4?"). Don't edit code until the user picks.

## Applying fixes

- `.vue` changes: delegate to the **vue-expert** subagent, as CLAUDE.md requires. Give it the finding text (where, what, suggested change) so it doesn't have to rediscover anything, and batch related findings into one brief.
- New or changed `.js` files (`composables/`, `utils/`, `main.js`, `api.js`): these can be edited directly. When a new composable or component replaces duplicated code, update every call site in the same change. Half-finished extractions leave two copies.
- Keep the behavior the same. These are refactors: same rendered output, same API calls (or fewer), same filter behavior.
- Verify afterwards: `cd client && npm run build` must pass. For changes to rendering or data flow, load the affected pages with the Playwright MCP tools against `http://localhost:3000` (start the servers with the `start` skill if needed) and check the browser console for errors.
- Add comments to any non-obvious changes, as CLAUDE.md asks.
