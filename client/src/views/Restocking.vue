<template>
  <div class="restocking">
    <div class="page-header">
      <p>{{ t('restocking.description') }}</p>
    </div>

    <div v-if="loading" class="loading">{{ t('common.loading') }}</div>
    <div v-else-if="error" class="error">{{ error }}</div>
    <div v-else>
      <!-- Budget slider -->
      <div class="card budget-card">
        <div class="budget-row">
          <label for="budget-slider" class="budget-label">{{ t('restocking.budget') }}</label>
          <span class="budget-value">{{ money(budget) }}</span>
        </div>
        <input
          id="budget-slider"
          v-model.number="budget"
          type="range"
          min="0"
          :max="maxBudget"
          step="50"
          class="budget-slider"
        />
        <div class="budget-scale">
          <span>{{ money(0) }}</span>
          <span>{{ money(maxBudget) }}</span>
        </div>
        <p class="budget-help">{{ t('restocking.budgetHelp') }}</p>
      </div>

      <!-- Summary cards -->
      <div class="stats-grid">
        <div class="stat-card info">
          <div class="stat-label">{{ t('restocking.itemsSelected') }}</div>
          <div class="stat-value">{{ summary.itemCount }}</div>
        </div>
        <div class="stat-card success">
          <div class="stat-label">{{ t('restocking.totalCost') }}</div>
          <div class="stat-value">{{ money(summary.totalCost) }}</div>
        </div>
        <div class="stat-card warning">
          <div class="stat-label">{{ t('restocking.budgetRemaining') }}</div>
          <div class="stat-value">{{ money(summary.remaining) }}</div>
        </div>
        <div class="stat-card info">
          <div class="stat-label">{{ t('restocking.leadTime') }}</div>
          <div class="stat-value">{{ t('restocking.days', { count: summary.leadTime }) }}</div>
        </div>
      </div>

      <!-- Confirmation / submit error -->
      <div v-if="confirmation" class="confirmation">
        <strong>{{ t('restocking.orderPlaced') }}</strong>
        <span>
          {{ t('restocking.orderPlacedDetail', {
            orderNumber: confirmation.order_number,
            date: formatDate(confirmation.expected_delivery)
          }) }}
        </span>
        <router-link to="/orders" class="confirmation-link">{{ t('restocking.viewOrders') }}</router-link>
      </div>
      <div v-if="submitError" class="error">{{ submitError }}</div>

      <div class="card">
        <div class="card-header header-with-action">
          <h3 class="card-title">{{ t('restocking.recommendations') }}</h3>
          <button
            type="button"
            class="place-order-btn"
            :disabled="!canSubmit"
            @click="placeOrder"
          >
            {{ submitting ? t('restocking.placing') : t('restocking.placeOrder') }}
          </button>
        </div>
        <div v-if="summary.itemCount === 0" class="empty-note">{{ t('restocking.noRecommendations') }}</div>
        <div class="table-container">
          <table>
            <thead>
              <tr>
                <th>{{ t('restocking.table.sku') }}</th>
                <th>{{ t('restocking.table.itemName') }}</th>
                <th>{{ t('restocking.table.trend') }}</th>
                <th class="num">{{ t('restocking.table.needed') }}</th>
                <th class="num">{{ t('restocking.table.recommended') }}</th>
                <th class="num">{{ t('restocking.table.unitCost') }}</th>
                <th class="num">{{ t('restocking.table.lineTotal') }}</th>
                <th class="num">{{ t('restocking.table.leadTime') }}</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="row in recommendations" :key="row.id" :class="{ dimmed: row.quantity === 0 }">
                <td><strong>{{ row.item_sku }}</strong></td>
                <td>{{ row.item_name }}</td>
                <td>
                  <span :class="['badge', row.trend]">{{ t(`trends.${row.trend}`) }}</span>
                </td>
                <td class="num">{{ row.needed }}</td>
                <td class="num">
                  <template v-if="row.quantity === 0">
                    <span class="not-included">{{ t('restocking.notIncluded') }}</span>
                  </template>
                  <template v-else>
                    <strong>{{ row.quantity }}</strong>
                    <span v-if="row.quantity < row.needed" class="badge warning partial-badge">{{ t('restocking.partial') }}</span>
                  </template>
                </td>
                <td class="num">{{ money(row.unit_cost, 2) }}</td>
                <td class="num">{{ row.quantity > 0 ? money(row.lineTotal, 2) : '-' }}</td>
                <td class="num">{{ row.lead_time_days }}</td>
              </tr>
            </tbody>
          </table>
        </div>
      </div>
    </div>
  </div>
</template>

<script>
import { ref, computed, watch, onMounted } from 'vue'
import { api } from '../api'
import { useI18n } from '../composables/useI18n'
import { formatCurrencyWithDecimals } from '../utils/currency'

// Lower rank = filled first
const TREND_RANK = { increasing: 0, stable: 1, decreasing: 2 }

export default {
  name: 'Restocking',
  setup() {
    const { t, currentCurrency, currentLocale } = useI18n()

    const loading = ref(true)
    const error = ref(null)
    const forecasts = ref([])
    const budget = ref(0)

    const submitting = ref(false)
    const submitError = ref(null)
    const confirmation = ref(null)

    const money = (amount, decimals = 0) => formatCurrencyWithDecimals(amount, currentCurrency.value, decimals)

    // Candidates: needed qty = forecast - current (never negative); skip items with
    // nothing needed or no usable unit cost. Sorted by trend, then larger need, then sku.
    const ranked = computed(() => {
      return forecasts.value
        .map(f => ({ ...f, needed: Math.max(0, f.forecasted_demand - f.current_demand) }))
        .filter(f => f.needed > 0 && f.unit_cost > 0)
        .sort((a, b) => {
          const trendDiff = (TREND_RANK[a.trend] ?? 3) - (TREND_RANK[b.trend] ?? 3)
          if (trendDiff !== 0) return trendDiff
          if (b.needed !== a.needed) return b.needed - a.needed
          return a.item_sku.localeCompare(b.item_sku)
        })
    })

    // Slider max: cost of fulfilling every need, rounded up to the next $500.
    const maxBudget = computed(() => {
      const total = ranked.value.reduce((sum, f) => sum + f.needed * f.unit_cost, 0)
      // Subtract a tiny epsilon so an exact multiple of 500 is not bumped up a whole step by float noise
      return Math.ceil((total - 1e-6) / 500) * 500
    })

    // Greedy fill. Money is tracked in integer cents so float error can never push
    // the total a cent over the budget (the server rejects totals above budget).
    const recommendations = computed(() => {
      let remainingCents = Math.round(budget.value * 100)
      return ranked.value.map(f => {
        const unitCents = Math.round(f.unit_cost * 100)
        let quantity = 0
        if (f.needed * unitCents <= remainingCents) {
          quantity = f.needed
        } else {
          // Partial fill with whatever whole units still fit; cheaper later items may still fit after this
          quantity = Math.floor(remainingCents / unitCents)
        }
        remainingCents -= quantity * unitCents
        return { ...f, quantity, lineTotal: (quantity * unitCents) / 100 }
      })
    })

    const included = computed(() => recommendations.value.filter(r => r.quantity > 0))

    const summary = computed(() => {
      const totalCents = included.value.reduce((sum, r) => sum + Math.round(r.lineTotal * 100), 0)
      return {
        itemCount: included.value.length,
        totalCost: totalCents / 100,
        remaining: Math.max(0, Math.round(budget.value * 100) - totalCents) / 100,
        leadTime: included.value.reduce((max, r) => Math.max(max, r.lead_time_days), 0)
      }
    })

    // Block resubmitting the same cart after success; moving the slider clears the confirmation (see watch below)
    const canSubmit = computed(() => included.value.length > 0 && !submitting.value && !confirmation.value)

    // A new budget means a new cart, so stale success/error banners no longer apply
    watch(budget, () => {
      confirmation.value = null
      submitError.value = null
    })

    const formatDate = (dateString) => {
      const date = new Date(dateString)
      // Guard against missing/invalid dates from the API
      if (isNaN(date.getTime())) return '-'
      return date.toLocaleDateString(currentLocale.value === 'ja' ? 'ja-JP' : 'en-US', {
        year: 'numeric',
        month: 'short',
        day: 'numeric'
      })
    }

    const loadForecasts = async () => {
      try {
        loading.value = true
        error.value = null
        forecasts.value = await api.getDemandForecasts()
        // Default to roughly half of max, snapped to the slider's $50 step
        budget.value = Math.round(maxBudget.value / 2 / 50) * 50
      } catch (err) {
        error.value = t('restocking.loadFailed') + ': ' + err.message
      } finally {
        loading.value = false
      }
    }

    const placeOrder = async () => {
      if (!canSubmit.value) return
      submitting.value = true
      submitError.value = null
      confirmation.value = null
      try {
        confirmation.value = await api.createRestockingOrder({
          items: included.value.map(r => ({ item_sku: r.item_sku, quantity: r.quantity })),
          budget: budget.value
        })
      } catch (err) {
        // Prefer the server's explanation (400 detail); 422 detail is an array, so fall back to the generic message
        const detail = err.response?.data?.detail
        submitError.value = typeof detail === 'string'
          ? detail
          : t('restocking.orderFailed') + (err.message ? ': ' + err.message : '')
      } finally {
        submitting.value = false
      }
    }

    onMounted(loadForecasts)

    return {
      t,
      loading,
      error,
      budget,
      maxBudget,
      recommendations,
      summary,
      canSubmit,
      submitting,
      submitError,
      confirmation,
      money,
      formatDate,
      placeOrder
    }
  }
}
</script>

<style scoped>
.budget-card {
  padding: 1.25rem 1.5rem;
  margin-bottom: 1.25rem;
}

.budget-row {
  display: flex;
  justify-content: space-between;
  align-items: baseline;
  margin-bottom: 0.75rem;
}

.budget-label {
  font-size: 0.875rem;
  font-weight: 600;
  color: #64748b;
  text-transform: uppercase;
  letter-spacing: 0.05em;
}

.budget-value {
  font-size: 1.5rem;
  font-weight: 700;
  color: #0f172a;
}

.budget-slider {
  width: 100%;
  accent-color: var(--color-accent);
}

.budget-scale {
  display: flex;
  justify-content: space-between;
  font-size: 0.75rem;
  color: #64748b;
}

.budget-help {
  margin-top: 0.75rem;
  font-size: 0.813rem;
  color: #64748b;
}

.header-with-action {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.place-order-btn {
  background: var(--color-accent);
  color: white;
  border: none;
  border-radius: var(--radius-md);
  padding: 0.5rem 1.25rem;
  font-size: 0.875rem;
  font-weight: 600;
  cursor: pointer;
  transition: background 0.15s ease;
}

.place-order-btn:hover:not(:disabled) {
  background: var(--color-accent-hover);
}

.place-order-btn:disabled {
  background: #cbd5e1;
  cursor: not-allowed;
}

.confirmation {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 0.75rem;
  background: #f0fdf4;
  border: 1px solid #bbf7d0;
  color: #166534;
  padding: 1rem;
  border-radius: 8px;
  margin-bottom: 1.25rem;
  font-size: 0.938rem;
}

.confirmation-link {
  color: #0f172a;
  font-weight: 600;
  text-decoration: underline;
}

.empty-note {
  padding: 1rem 1.5rem;
  color: #64748b;
  font-size: 0.875rem;
}

.num {
  text-align: right;
}

tr.dimmed td {
  opacity: 0.45;
}

.not-included {
  font-style: italic;
  color: #64748b;
}

.partial-badge {
  margin-left: 0.5rem;
}
</style>
