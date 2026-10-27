<template>
  <div class="app" :class="{ 'sidebar-collapsed': isCollapsed, 'drawer-open': drawerOpen }">
    <div
      v-if="isMobile && drawerOpen"
      class="sidebar-backdrop"
      aria-hidden="true"
      @click="dismissDrawer"
    ></div>

    <aside
      id="app-sidebar"
      ref="sidebarRef"
      class="sidebar"
      :class="{ collapsed: isCollapsed, open: drawerOpen }"
    >
      <div class="sidebar-brand">
        <div class="brand-mark" aria-hidden="true">{{ brandInitial }}</div>
        <div v-show="!isCollapsed" class="brand-text">
          <span class="brand-name">{{ t('nav.companyName') }}</span>
          <span class="brand-sub">{{ t('nav.subtitle') }}</span>
        </div>
      </div>

      <nav class="sidebar-nav" :aria-label="t('nav.mainNavigation')">
        <router-link
          v-for="item in navItems"
          :key="item.path"
          :to="item.path"
          class="nav-item"
          :class="{ active: $route.path === item.path }"
          :aria-label="isCollapsed ? t(item.labelKey) : undefined"
          :title="isCollapsed ? t(item.labelKey) : undefined"
          :aria-current="$route.path === item.path ? 'page' : undefined"
        >
          <svg
            class="nav-icon"
            viewBox="0 0 24 24"
            fill="none"
            stroke="currentColor"
            stroke-width="1.75"
            stroke-linecap="round"
            stroke-linejoin="round"
            aria-hidden="true"
            v-html="icons[item.icon]"
          ></svg>
          <span v-show="!isCollapsed" class="nav-label">{{ t(item.labelKey) }}</span>
        </router-link>
      </nav>

      <div class="sidebar-footer">
        <button
          v-if="!isMobile"
          type="button"
          class="collapse-toggle"
          :aria-label="isCollapsed ? t('nav.expandSidebar') : t('nav.collapseSidebar')"
          :title="isCollapsed ? t('nav.expandSidebar') : t('nav.collapseSidebar')"
          :aria-expanded="!isCollapsed"
          aria-controls="app-sidebar"
          @click="toggleCollapsed"
        >
          <svg class="nav-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.75" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
            <rect x="3" y="4" width="18" height="16" rx="2"/>
            <path d="M9 4v16"/>
            <path :d="isCollapsed ? 'M14 10l2 2-2 2' : 'M16 10l-2 2 2 2'"/>
          </svg>
          <span v-show="!isCollapsed" class="nav-label">{{ t('nav.collapseSidebar') }}</span>
        </button>

        <button
          type="button"
          class="sidebar-user"
          :aria-label="isCollapsed ? currentUser.name : undefined"
          :title="isCollapsed ? currentUser.name : undefined"
          @click="openProfileFromSidebar"
        >
          <span class="user-avatar" aria-hidden="true">{{ userInitials }}</span>
          <span v-show="!isCollapsed" class="user-meta">
            <span class="user-name">{{ currentUser.name }}</span>
            <span class="user-role">{{ currentUser.jobTitle }}</span>
          </span>
        </button>
      </div>
    </aside>

    <div class="app-main">
      <header class="top-bar">
        <button
          ref="menuButtonRef"
          type="button"
          class="menu-button"
          :aria-label="t('nav.openMenu')"
          :aria-expanded="drawerOpen"
          aria-controls="app-sidebar"
          @click="openDrawer"
        >
          <svg viewBox="0 0 24 24" width="20" height="20" fill="none" stroke="currentColor" stroke-width="1.75" stroke-linecap="round" aria-hidden="true">
            <path d="M4 6h16M4 12h16M4 18h16"/>
          </svg>
        </button>
        <h1 class="top-bar-title">{{ pageTitle }}</h1>
        <div class="top-bar-actions">
          <LanguageSwitcher />
          <ProfileMenu
            @show-profile-details="showProfileDetails = true"
            @show-tasks="showTasks = true"
          />
        </div>
      </header>
      <FilterBar />
      <main class="main-content">
        <router-view />
      </main>
    </div>

    <ProfileDetailsModal
      :is-open="showProfileDetails"
      @close="showProfileDetails = false"
    />

    <TasksModal
      :is-open="showTasks"
      :tasks="tasks"
      @close="showTasks = false"
      @add-task="addTask"
      @delete-task="deleteTask"
      @toggle-task="toggleTask"
    />
  </div>
</template>

<script>
import { ref, nextTick, onMounted, onBeforeUnmount, computed, watch } from 'vue'
import { useRoute } from 'vue-router'
import { api } from './api'
import { useAuth } from './composables/useAuth'
import { useI18n } from './composables/useI18n'
import FilterBar from './components/FilterBar.vue'
import ProfileMenu from './components/ProfileMenu.vue'
import ProfileDetailsModal from './components/ProfileDetailsModal.vue'
import TasksModal from './components/TasksModal.vue'
import LanguageSwitcher from './components/LanguageSwitcher.vue'

const COLLAPSED_KEY = 'sidebarCollapsed'
const MOBILE_QUERY = '(max-width: 768px)'

// Stroke-style 24x24 icon paths (inline SVG, currentColor); static trusted strings, never user input
const icons = {
  overview: '<rect x="3" y="3" width="7" height="9" rx="1.5"/><rect x="14" y="3" width="7" height="5" rx="1.5"/><rect x="14" y="12" width="7" height="9" rx="1.5"/><rect x="3" y="16" width="7" height="5" rx="1.5"/>',
  inventory: '<path d="M21 8l-9-5-9 5 9 5 9-5z"/><path d="M3 8v8l9 5 9-5V8"/><path d="M12 13v8"/>',
  orders: '<path d="M6 3h12l2 4v13a1 1 0 01-1 1H5a1 1 0 01-1-1V7l2-4z"/><path d="M4 7h16"/><path d="M9 11a3 3 0 006 0"/>',
  finance: '<path d="M12 2v20"/><path d="M17 6.5C17 4.9 14.8 4 12 4S7 5 7 7c0 4.5 10 2 10 7 0 2-2.2 3-5 3s-5-.9-5-2.5"/>',
  demand: '<path d="M3 3v18h18"/><path d="M7 15l4-4 3 3 5-6"/>',
  restocking: '<path d="M21 12a9 9 0 11-3-6.7"/><path d="M21 3v6h-6"/>',
  reports: '<path d="M14 3H7a2 2 0 00-2 2v14a2 2 0 002 2h10a2 2 0 002-2V8l-5-5z"/><path d="M14 3v5h5"/><path d="M9 13h6M9 17h6"/>'
}

const navItems = [
  { path: '/', icon: 'overview', labelKey: 'nav.overview' },
  { path: '/inventory', icon: 'inventory', labelKey: 'nav.inventory' },
  { path: '/orders', icon: 'orders', labelKey: 'nav.orders' },
  { path: '/spending', icon: 'finance', labelKey: 'nav.finance' },
  { path: '/demand', icon: 'demand', labelKey: 'nav.demandForecast' },
  { path: '/restocking', icon: 'restocking', labelKey: 'nav.restocking' },
  { path: '/reports', icon: 'reports', labelKey: 'nav.reports' }
]

// localStorage can throw (private mode, blocked storage); fall back to in-memory state
const readCollapsed = () => {
  try {
    return localStorage.getItem(COLLAPSED_KEY) === 'true'
  } catch (err) {
    return false
  }
}

const writeCollapsed = (value) => {
  try {
    localStorage.setItem(COLLAPSED_KEY, String(value))
  } catch (err) {
    // Storage unavailable: the toggle still works for this session
  }
}

export default {
  name: 'App',
  components: {
    FilterBar,
    ProfileMenu,
    ProfileDetailsModal,
    TasksModal,
    LanguageSwitcher
  },
  setup() {
    const { currentUser } = useAuth()
    const { t } = useI18n()
    const route = useRoute()
    const showProfileDetails = ref(false)
    const showTasks = ref(false)
    const apiTasks = ref([])

    const collapsedPref = ref(readCollapsed())
    const isMobile = ref(false)
    const drawerOpen = ref(false)

    // The drawer is always full-width with labels, so the collapsed preference only applies on desktop
    const isCollapsed = computed(() => collapsedPref.value && !isMobile.value)

    const toggleCollapsed = () => {
      collapsedPref.value = !collapsedPref.value
      writeCollapsed(collapsedPref.value)
    }

    const openDrawer = () => { drawerOpen.value = true }
    const closeDrawer = () => { drawerOpen.value = false }

    // Focus management for the mobile drawer. The closed drawer is visibility:hidden (see CSS),
    // so focus must be moved in explicitly on open and handed back to the toggle on dismiss.
    const sidebarRef = ref(null)
    const menuButtonRef = ref(null)

    // Used for Escape/backdrop: close and return focus to the hamburger button.
    // Navigation and profile actions use plain closeDrawer so they don't steal focus.
    const dismissDrawer = () => {
      closeDrawer()
      nextTick(() => menuButtonRef.value && menuButtonRef.value.focus())
    }

    const onKeydown = (e) => {
      if (e.key === 'Escape' && drawerOpen.value) dismissDrawer()
    }

    let mediaQuery = null
    const onMediaChange = (e) => {
      isMobile.value = e.matches
      // Leaving mobile layout must not leave a stale open drawer
      if (!e.matches) drawerOpen.value = false
    }

    // Close the drawer after navigating
    watch(() => route.path, closeDrawer)

    // Lock body scroll while the drawer overlays the page
    watch(drawerOpen, (open) => {
      document.body.style.overflow = open ? 'hidden' : ''
      if (open) {
        // Visibility flips to visible immediately on open (no delay), so focus can move once DOM updates
        nextTick(() => {
          const first = sidebarRef.value && sidebarRef.value.querySelector('.nav-item')
          if (first) first.focus()
        })
      }
    })

    const pageTitles = {
      '/': 'nav.overview',
      '/inventory': 'nav.inventory',
      '/orders': 'nav.orders',
      '/spending': 'nav.finance',
      '/demand': 'nav.demandForecast',
      '/restocking': 'nav.restocking',
      '/reports': 'nav.reports'
    }

    const pageTitle = computed(() => t(pageTitles[route.path] || 'nav.companyName'))

    const brandInitial = computed(() => (t('nav.companyName') || '').trim().charAt(0).toUpperCase())

    const userInitials = computed(() => {
      const parts = (currentUser.value.name || '').split(' ').filter(Boolean)
      return parts.map(p => p[0]).join('').slice(0, 2).toUpperCase()
    })

    const openProfileFromSidebar = () => {
      showProfileDetails.value = true
      closeDrawer()
    }

    // Merge mock tasks from currentUser with API tasks
    const tasks = computed(() => {
      return [...currentUser.value.tasks, ...apiTasks.value]
    })

    const loadTasks = async () => {
      try {
        apiTasks.value = await api.getTasks()
      } catch (err) {
        console.error('Failed to load tasks:', err)
      }
    }

    const addTask = async (taskData) => {
      try {
        const newTask = await api.createTask(taskData)
        // Add new task to the beginning of the array
        apiTasks.value.unshift(newTask)
      } catch (err) {
        console.error('Failed to add task:', err)
      }
    }

    const deleteTask = async (taskId) => {
      try {
        // Check if it's a mock task (from currentUser)
        const isMockTask = currentUser.value.tasks.some(t => t.id === taskId)

        if (isMockTask) {
          // Remove from mock tasks
          const index = currentUser.value.tasks.findIndex(t => t.id === taskId)
          if (index !== -1) {
            currentUser.value.tasks.splice(index, 1)
          }
        } else {
          // Remove from API tasks
          await api.deleteTask(taskId)
          apiTasks.value = apiTasks.value.filter(t => t.id !== taskId)
        }
      } catch (err) {
        console.error('Failed to delete task:', err)
      }
    }

    const toggleTask = async (taskId) => {
      try {
        // Check if it's a mock task (from currentUser)
        const mockTask = currentUser.value.tasks.find(t => t.id === taskId)

        if (mockTask) {
          // Toggle mock task status
          mockTask.status = mockTask.status === 'pending' ? 'completed' : 'pending'
        } else {
          // Toggle API task
          const updatedTask = await api.toggleTask(taskId)
          const index = apiTasks.value.findIndex(t => t.id === taskId)
          if (index !== -1) {
            apiTasks.value[index] = updatedTask
          }
        }
      } catch (err) {
        console.error('Failed to toggle task:', err)
      }
    }

    onMounted(() => {
      loadTasks()
      document.addEventListener('keydown', onKeydown)
      if (window.matchMedia) {
        mediaQuery = window.matchMedia(MOBILE_QUERY)
        isMobile.value = mediaQuery.matches
        mediaQuery.addEventListener('change', onMediaChange)
      }
    })

    onBeforeUnmount(() => {
      document.removeEventListener('keydown', onKeydown)
      if (mediaQuery) mediaQuery.removeEventListener('change', onMediaChange)
      document.body.style.overflow = ''
    })

    return {
      t,
      currentUser,
      icons,
      navItems,
      showProfileDetails,
      showTasks,
      tasks,
      addTask,
      deleteTask,
      toggleTask,
      isCollapsed,
      isMobile,
      drawerOpen,
      toggleCollapsed,
      openDrawer,
      closeDrawer,
      dismissDrawer,
      sidebarRef,
      menuButtonRef,
      pageTitle,
      brandInitial,
      userInitials,
      openProfileFromSidebar
    }
  }
}
</script>

<style>
/* ---------- Design tokens ---------- */
:root {
  /* Accent */
  --color-accent: #4f46e5;
  --color-accent-hover: #4338ca;
  --color-accent-soft: #eef2ff;
  --color-accent-ring: rgba(79, 70, 229, 0.25);

  /* Neutrals */
  --color-bg: #f8fafc;
  --color-surface: #ffffff;
  --color-border: #e2e8f0;
  --color-border-strong: #cbd5e1;
  --color-text: #1e293b;
  --color-text-strong: #0f172a;
  --color-text-muted: #64748b;
  --color-row-hover: #f8fafc;

  /* Status (semantic, unchanged) */
  --color-success: #059669;
  --color-success-bg: #d1fae5;
  --color-success-text: #065f46;
  --color-info: #2563eb;
  --color-info-bg: #dbeafe;
  --color-info-text: #1e40af;
  --color-warning: #ea580c;
  --color-warning-bg: #fed7aa;
  --color-warning-text: #92400e;
  --color-danger: #dc2626;
  --color-danger-bg: #fecaca;
  --color-danger-text: #991b1b;

  /* Sidebar */
  --sidebar-bg: #0f172a;
  --sidebar-border: #1e293b;
  --sidebar-text: #94a3b8;
  --sidebar-text-hover: #e2e8f0;
  --sidebar-hover-bg: rgba(148, 163, 184, 0.1);
  --sidebar-active-bg: rgba(99, 102, 241, 0.18);
  --sidebar-active-text: #ffffff;
  --sidebar-indicator: #818cf8;
  --sidebar-width: 240px;
  --sidebar-width-collapsed: 72px;

  /* Shape and elevation */
  --radius-sm: 6px;
  --radius-md: 8px;
  --radius-lg: 12px;
  --shadow-sm: 0 1px 2px rgba(15, 23, 42, 0.05);
  --shadow-md: 0 4px 12px rgba(15, 23, 42, 0.08);

  /* Spacing scale */
  --space-1: 0.25rem;
  --space-2: 0.5rem;
  --space-3: 0.75rem;
  --space-4: 1rem;
  --space-5: 1.25rem;
  --space-6: 1.5rem;
  --space-8: 2rem;

  /* Layout */
  --topbar-height: 64px;
  --content-max-width: 1600px;
  --page-padding: 2rem;
  --transition: 0.15s ease;
}

* {
  margin: 0;
  padding: 0;
  box-sizing: border-box;
}

body {
  font-family: 'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Oxygen, Ubuntu, Cantarell, sans-serif;
  background: var(--color-bg);
  color: var(--color-text);
  -webkit-font-smoothing: antialiased;
  -moz-osx-font-smoothing: grayscale;
}

:focus-visible {
  outline: 2px solid var(--color-accent);
  outline-offset: 2px;
}

/* ---------- App shell ---------- */
.app {
  display: flex;
  min-height: 100vh;
}

.app-main {
  flex: 1;
  min-width: 0; /* allow wide tables/charts to scroll instead of stretching the flex item */
  display: flex;
  flex-direction: column;
}

.sidebar {
  position: sticky;
  top: 0;
  height: 100vh;
  flex-shrink: 0;
  width: var(--sidebar-width);
  background: var(--sidebar-bg);
  color: var(--sidebar-text);
  display: flex;
  flex-direction: column;
  transition: width 0.2s ease;
  z-index: 200;
  overflow: hidden;
}

.sidebar.collapsed {
  width: var(--sidebar-width-collapsed);
}

.sidebar-brand {
  display: flex;
  align-items: center;
  gap: var(--space-3);
  height: var(--topbar-height);
  padding: 0 1.25rem;
  border-bottom: 1px solid var(--sidebar-border);
  flex-shrink: 0;
}

.brand-mark {
  width: 32px;
  height: 32px;
  flex-shrink: 0;
  border-radius: var(--radius-md);
  background: var(--color-accent);
  color: #fff;
  display: flex;
  align-items: center;
  justify-content: center;
  font-weight: 700;
  font-size: 0.938rem;
}

.brand-text {
  display: flex;
  flex-direction: column;
  min-width: 0;
}

.brand-name {
  color: #f8fafc;
  font-weight: 700;
  font-size: 0.938rem;
  letter-spacing: -0.01em;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.brand-sub {
  font-size: 0.688rem;
  color: var(--sidebar-text);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.sidebar-nav {
  flex: 1;
  overflow-y: auto;
  padding: var(--space-4) var(--space-3);
  display: flex;
  flex-direction: column;
  gap: var(--space-1);
}

.nav-item,
.collapse-toggle,
.sidebar-user {
  position: relative;
  display: flex;
  align-items: center;
  gap: var(--space-3);
  width: 100%;
  height: 42px;
  padding: 0 0.875rem;
  border: none;
  border-radius: var(--radius-md);
  background: transparent;
  color: var(--sidebar-text);
  font: inherit;
  font-size: 0.875rem;
  font-weight: 500;
  text-decoration: none;
  text-align: left;
  cursor: pointer;
  transition: background var(--transition), color var(--transition);
}

.sidebar.collapsed .nav-item,
.sidebar.collapsed .collapse-toggle,
.sidebar.collapsed .sidebar-user {
  justify-content: center;
  padding: 0;
}

.nav-item:hover,
.collapse-toggle:hover,
.sidebar-user:hover {
  background: var(--sidebar-hover-bg);
  color: var(--sidebar-text-hover);
}

.nav-item.active {
  background: var(--sidebar-active-bg);
  color: var(--sidebar-active-text);
}

/* Indigo indicator bar on the active item */
.nav-item.active::before {
  content: '';
  position: absolute;
  left: -0.75rem;
  top: 8px;
  bottom: 8px;
  width: 3px;
  border-radius: 0 3px 3px 0;
  background: var(--sidebar-indicator);
}

.nav-item:focus-visible,
.collapse-toggle:focus-visible,
.sidebar-user:focus-visible {
  outline-color: var(--sidebar-indicator);
  outline-offset: -2px;
}

.nav-icon {
  width: 20px;
  height: 20px;
  flex-shrink: 0;
}

.nav-label {
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.sidebar-footer {
  flex-shrink: 0;
  padding: var(--space-3);
  border-top: 1px solid var(--sidebar-border);
  display: flex;
  flex-direction: column;
  gap: var(--space-1);
}

.sidebar-user {
  height: 52px;
  padding: 0 var(--space-2);
}

.user-avatar {
  width: 32px;
  height: 32px;
  flex-shrink: 0;
  border-radius: 50%;
  background: #312e81;
  color: #e0e7ff;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 0.75rem;
  font-weight: 600;
}

.user-meta {
  display: flex;
  flex-direction: column;
  min-width: 0;
}

.sidebar-user .user-name {
  color: #e2e8f0;
  font-size: 0.813rem;
  font-weight: 600;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.user-role {
  font-size: 0.688rem;
  color: var(--sidebar-text);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.sidebar-backdrop {
  position: fixed;
  inset: 0;
  background: rgba(15, 23, 42, 0.55);
  z-index: 150;
}

/* ---------- Top bar ---------- */
.top-bar {
  position: sticky;
  top: 0;
  z-index: 100;
  height: var(--topbar-height);
  display: flex;
  align-items: center;
  gap: var(--space-4);
  padding: 0 var(--page-padding);
  background: var(--color-surface);
  border-bottom: 1px solid var(--color-border);
}

.top-bar-title {
  font-size: 1.125rem;
  font-weight: 700;
  color: var(--color-text-strong);
  letter-spacing: -0.02em;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  min-width: 0;
}

.top-bar-actions {
  margin-left: auto;
  display: flex;
  align-items: center;
  gap: var(--space-3);
  flex-shrink: 0;
}

.menu-button {
  display: none;
  align-items: center;
  justify-content: center;
  width: 40px;
  height: 40px;
  flex-shrink: 0;
  background: var(--color-surface);
  border: 1px solid var(--color-border);
  border-radius: var(--radius-md);
  color: var(--color-text-strong);
  cursor: pointer;
}

.menu-button:hover {
  background: var(--color-bg);
}

.main-content {
  flex: 1;
  width: 100%;
  max-width: var(--content-max-width);
  margin: 0 auto;
  padding: var(--space-6) var(--page-padding);
}

@media (max-width: 768px) {
  :root {
    --page-padding: 1rem;
  }

  .menu-button {
    display: inline-flex;
  }

  /* Off-canvas drawer; slides over content instead of taking layout space */
  .sidebar {
    position: fixed;
    left: 0;
    top: 0;
    bottom: 0;
    width: min(280px, 85vw);
    transform: translateX(-100%);
    /* Hidden when closed so Tab cannot reach nav links; visibility flips only after the slide-out ends */
    visibility: hidden;
    transition: transform 0.25s ease, visibility 0s linear 0.25s;
    box-shadow: none;
  }

  .sidebar.open {
    transform: translateX(0);
    visibility: visible;
    transition: transform 0.25s ease, visibility 0s linear 0s;
    box-shadow: 0 0 40px rgba(0, 0, 0, 0.35);
  }

  /* Keep the language and profile labels from crowding the title on narrow screens */
  .top-bar-actions .profile-name,
  .top-bar-actions .language-label {
    display: none;
  }
}

@media (prefers-reduced-motion: reduce) {
  .sidebar { transition: none; }
  /* Visibility delay must also go, or the closed drawer stays focusable briefly */
  @media (max-width: 768px) {
    .sidebar,
    .sidebar.open { transition: none; }
  }
}

/* ---------- Page header ---------- */
.page-header {
  margin-bottom: var(--space-6);
}

.page-header h2 {
  font-size: 1.75rem;
  font-weight: 700;
  color: var(--color-text-strong);
  margin-bottom: 0.375rem;
  letter-spacing: -0.025em;
}

.page-header p {
  color: var(--color-text-muted);
  font-size: 0.938rem;
}

/* ---------- Stat / KPI tiles ---------- */
.stats-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(240px, 1fr));
  gap: var(--space-5);
  margin-bottom: var(--space-6);
}

.stat-card {
  background: var(--color-surface);
  padding: var(--space-5);
  border-radius: var(--radius-lg);
  border: 1px solid var(--color-border);
  box-shadow: var(--shadow-sm);
  transition: border-color var(--transition), box-shadow var(--transition);
}

.stat-card:hover {
  border-color: var(--color-border-strong);
  box-shadow: var(--shadow-md);
}

.stat-label {
  color: var(--color-text-muted);
  font-size: 0.75rem;
  font-weight: 600;
  text-transform: uppercase;
  letter-spacing: 0.05em;
  margin-bottom: var(--space-2);
}

.stat-value {
  font-size: 2rem;
  font-weight: 700;
  color: var(--color-text-strong);
  letter-spacing: -0.025em;
}

.stat-card.warning .stat-value { color: var(--color-warning); }
.stat-card.success .stat-value { color: var(--color-success); }
.stat-card.danger .stat-value { color: var(--color-danger); }
.stat-card.info .stat-value { color: var(--color-info); }

/* ---------- Cards ---------- */
.card {
  background: var(--color-surface);
  border-radius: var(--radius-lg);
  padding: var(--space-5);
  border: 1px solid var(--color-border);
  box-shadow: var(--shadow-sm);
  margin-bottom: var(--space-5);
}

.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: var(--space-4);
  padding-bottom: 0.875rem;
  border-bottom: 1px solid var(--color-border);
}

.card-title {
  font-size: 1.063rem;
  font-weight: 700;
  color: var(--color-text-strong);
  letter-spacing: -0.02em;
}

/* ---------- Tables ---------- */
.table-container {
  overflow-x: auto;
}

table {
  width: 100%;
  border-collapse: collapse;
}

thead {
  background: var(--color-bg);
  border-top: 1px solid var(--color-border);
  border-bottom: 1px solid var(--color-border);
}

/* Cells carry the header background so it stays opaque if a view makes thead sticky */
th {
  text-align: left;
  padding: 0.625rem 0.875rem;
  font-weight: 600;
  color: #475569;
  background: var(--color-bg);
  font-size: 0.75rem;
  text-transform: uppercase;
  letter-spacing: 0.05em;
  white-space: nowrap;
}

td {
  padding: 0.75rem 0.875rem;
  border-top: 1px solid #f1f5f9;
  color: #334155;
  font-size: 0.875rem;
}

tbody tr {
  transition: background-color var(--transition);
}

tbody tr:hover {
  background: var(--color-row-hover);
}

/* ---------- Badges ---------- */
.badge {
  display: inline-block;
  padding: 0.25rem 0.625rem;
  border-radius: 999px;
  font-size: 0.688rem;
  font-weight: 600;
  text-transform: uppercase;
  letter-spacing: 0.04em;
}

.badge.success,
.badge.increasing { background: var(--color-success-bg); color: var(--color-success-text); }
.badge.warning,
.badge.medium { background: var(--color-warning-bg); color: var(--color-warning-text); }
.badge.danger,
.badge.decreasing,
.badge.high { background: var(--color-danger-bg); color: var(--color-danger-text); }
.badge.info,
.badge.low { background: var(--color-info-bg); color: var(--color-info-text); }
.badge.stable { background: var(--color-accent-soft); color: #3730a3; }

/* ---------- Buttons ---------- */
.btn {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  gap: var(--space-2);
  padding: 0.5rem 1rem;
  border-radius: var(--radius-md);
  border: 1px solid transparent;
  font: inherit;
  font-size: 0.875rem;
  font-weight: 600;
  cursor: pointer;
  text-decoration: none;
  transition: background var(--transition), border-color var(--transition), color var(--transition);
}

.btn:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.btn-primary {
  background: var(--color-accent);
  color: #fff;
}

.btn-primary:hover:not(:disabled) {
  background: var(--color-accent-hover);
}

.btn-secondary {
  background: var(--color-surface);
  color: var(--color-text-strong);
  border-color: var(--color-border-strong);
}

.btn-secondary:hover:not(:disabled) {
  background: var(--color-bg);
  border-color: var(--color-text-muted);
}

/* ---------- Form controls ---------- */
/* :where() keeps specificity at zero so view-level styles can still override */
:where(select, textarea, input:not([type='range'], [type='checkbox'], [type='radio'], [type='file'])) {
  font: inherit;
  font-size: 0.875rem;
  color: var(--color-text-strong);
  background: var(--color-surface);
  border: 1px solid var(--color-border-strong);
  border-radius: var(--radius-md);
  padding: 0.5rem 0.75rem;
  transition: border-color var(--transition), box-shadow var(--transition);
}

:where(select, textarea, input):focus {
  outline: none;
  border-color: var(--color-accent);
  box-shadow: 0 0 0 3px var(--color-accent-ring);
}

input[type='range'] {
  accent-color: var(--color-accent);
}

/* ---------- Feedback ---------- */
.loading {
  text-align: center;
  padding: 3rem;
  color: var(--color-text-muted);
  font-size: 0.938rem;
}

.error {
  background: #fef2f2;
  border: 1px solid var(--color-danger-bg);
  color: var(--color-danger-text);
  padding: var(--space-4);
  border-radius: var(--radius-md);
  margin: var(--space-4) 0;
  font-size: 0.938rem;
}
</style>
