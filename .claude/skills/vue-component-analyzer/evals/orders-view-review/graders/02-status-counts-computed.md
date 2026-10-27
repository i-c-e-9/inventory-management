---
type: llm
focus: trace
weight: 1
---

The report recommends replacing the repeated getOrdersByStatus() calls in the stat cards (Orders.vue lines 13-25) with a single computed (e.g. counts by status) so the list isn't filtered four times per render.
