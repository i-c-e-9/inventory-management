# Vue component checklist

Work through both sections for each component in scope. Each item lists what to look for, why it matters, and the fix to recommend. Not every item applies to every file. Skip what doesn't apply.

## Contents
- Performance: rendering, reactivity, data fetching, loading
- Reuse: logic, markup, styles, size and responsibility
- Judgment calls

---

## Performance

### Rendering

**`v-for` keys.** `:key="index"` (or `i`, `idx`) or a missing key on a list that can be filtered, sorted, or added to. Vue then patches DOM nodes in place by position, so component state and transitions end up on the wrong row. Index keys are also a CLAUDE.md rule violation. *Fix:* key by a stable id such as `sku`, `id`, `order_number` or `month`. Index keys on a static list that never reorders still break the project rule, but they're Low severity.

**`v-if` and `v-for` on the same element.** In Vue 3, `v-if` runs first, so it can't see the loop variable. That's either a bug or confusing code. *Fix:* filter in a computed and loop over that, or move `v-if` onto a wrapping `<template>`.

**Work in the template.** `{{ formatThing(x) }}` or `v-for="item in items.filter(...)"` runs again on every render of the component, not only when its inputs change. That matters inside large `v-for` loops or for expensive work (sorting, reduce over arrays, date parsing). *Fix:* move it into a computed, or precompute the formatted fields once in a computed list. Cheap formatting (`toFixed`, a currency call) on a handful of values is fine. Leave it alone.

**Child props that change identity every render.** Inline object/array literals or arrow functions passed as props (`:options="{...}"`, `:items="list.filter(...)"`) give the child a new value every render, so the child re-renders too. Only worth flagging when the child is expensive (a chart, a big table). *Fix:* hoist into a computed or a constant.

**Mounting heavy UI that's hidden.** Modals or panels kept in the DOM with `v-show` while closed, or many modals mounted up front. *Fix:* use `v-if` for rarely opened UI, and consider `defineAsyncComponent` for big modals so their code loads when first opened.

**Static content.** Large blocks that never change can use `v-once`, and rows that rarely change inside huge lists can use `v-memo`. This is a micro-optimization, so report it as Low and only for big lists.

### Reactivity

**Mutating reactive data inside a computed.** `.sort()`, `.reverse()` and `.splice()` mutate arrays in place. Inside a computed, or on an array that's also stored in a ref, they change the source data, can trigger extra updates, and make other consumers see a reordered list. This is a correctness bug, not just a perf issue. *Fix:* sort a copy (`[...arr].sort()`, `arr.slice().sort()`, or `toSorted()`). Chains like `.filter(...).sort(...)` or `.map(...).sort(...)` already work on a new array, so they're fine.

**Watchers that should be computeds.** A `watch` that only sets another ref from its source (`watch(a, v => b.value = f(v))`) adds an extra state copy and an extra update pass. *Fix:* use `const b = computed(() => f(a.value))`.

**Deep watchers.** `deep: true` on large objects or arrays walks the whole structure on every change. *Fix:* watch the specific fields, or a getter that returns them.

**Too much deep reactivity.** Big API payloads that are replaced wholesale and never mutated item by item still get a deep reactive proxy on every nested object. *Fix:* use `shallowRef` for the raw data. Only worth raising for large payloads (hundreds of rows or more).

**Unpaired side effects.** `addEventListener`, `setInterval` or observers created in `onMounted`/`setup` with no matching cleanup in `onUnmounted` leak across navigations. *Fix:* clean up in `onUnmounted`, or use a composable that does it.

### Data fetching

**Request waterfalls.** Independent `await`s run one after another (`const a = await api.x(); const b = await api.y()`) take the sum of their latencies. *Fix:* `const [a, b] = await Promise.all([api.x(), api.y()])`.

**Refetching the same data.** Several views call the same `api.*` method on mount, or a watcher refetches when unrelated state changes, or two watchers fire for the same filter change. *Fix:* fetch once with the right watch sources, or move shared server state into a composable that caches per filter set.

**Fetching in the wrong layer.** Filtering or aggregating data client-side that the API already supports through query params (see the API endpoints list in CLAUDE.md). *Fix:* pass the filter to `api.js` and let FastAPI do it.

### Loading

**Eagerly imported routes.** Static `import View from './views/View.vue'` in `main.js` puts every page into the initial bundle. *Fix:* `component: () => import('./views/View.vue')`. This is cheap and safe, so it's usually a High-payoff, S-effort finding when routes are eager.

---

## Reuse

### Logic

**Helpers that already exist.** A component defines a local `formatCurrency`, date formatter, status-color map or the like that duplicates something in `utils/` or `composables/`. Local copies drift (different rounding, currency symbol, locale). *Fix:* import the shared helper. If the local version adds something, extend the shared one.

**The same function in several components.** Same or near-same function bodies across files (formatters, status-to-class maps, date helpers, chart scaling math). *Fix:* move it to `utils/` (pure functions) or `composables/` (anything using refs or lifecycle).

**Repeated fetch/loading/error state.** Many views have the same `loading`/`error`/`data` refs, try/catch/finally around an `api.*` call, and a `watch` on the filters that refetches. *Fix:* a composable like `useFilteredFetch(fetcher)` that returns `{ data, loading, error, reload }` and watches `useFilters` itself. Show what the call site would look like.

**Bypassing shared state.** A component reimplements filter, i18n or auth logic instead of using `useFilters`, `useI18n` or `useAuth`. *Fix:* use the composable.

### Markup

**Copied component shells.** Several components share the same outer structure, such as modal overlay, header, close button, body and footer, or a stat card, table wrapper, status badge or empty state. *Fix:* a base component with slots (`BaseModal` with `#header`, default and `#footer` slots, and `v-model` for open/close), then rebuild the copies on top of it. Count the copies and the lines that would be removed.

**Repeated template blocks within one file.** The same 10+ lines of markup repeated with different data. *Fix:* loop over a config array, or extract a small local component.

### Styles

**The same CSS in many scoped blocks.** Identical rules (modal overlay, card, table, badge colors) copied across `<style scoped>` sections. *Fix:* move them to the global styles and design tokens in `App.vue` (project convention). Keep only truly component-specific rules scoped.

**Hardcoded colors.** Hex values that match the design system (`#0f172a`, `#64748b`, `#e2e8f0`, status colors) written inline instead of using the tokens. Low severity, but group them into one finding.

### Size and responsibility

**Oversized components.** As a rough guide, a component over about 500 lines, or one that mixes several unrelated sections (for example a dashboard with KPI cards, multiple charts and tables), is hard to change safely. Every bit of its reactive state re-renders the whole template. *Fix:* split it into child components along the visual sections, so each child re-renders only when its own props change. Name the proposed components and the props each one would take.

---

## Judgment calls

- **Do the arithmetic.** A computed over 20 rows isn't a perf problem. Use the actual data sizes in `server/data/*.json` when judging list sizes.
- **Don't recommend libraries** (Pinia, VueUse, virtual scrollers) unless the problem actually needs them. The project deliberately keeps dependencies small. A local composable is usually enough.
- **Suggest only behavior-preserving refactors.** If a fix would change what the user sees or which requests go out (beyond removing duplicates), say so explicitly.
- **Duplication is only worth extracting** when the copies really are the same concept and will change together. Two similar but separate things should stay separate.
