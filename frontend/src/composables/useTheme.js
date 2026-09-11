import { ref } from 'vue'

/**
 * Single source of truth for the Light / Dark theme.
 *
 * DESIGN.md ("Theme Architecture" and "Light Mode Compatibility") requires the
 * active theme to live on the document root as `data-theme`, to be persisted under
 * the `sj-select-theme` key, and to default to Light Mode when nothing is saved.
 *
 * `frontend/index.html` runs the same boot logic inline before the app renders so
 * the first paint never flashes the wrong theme; `applyStoredTheme()` performs the
 * same work for dev/SSR-less entry points.
 */

export const THEME_STORAGE_KEY = 'sj-select-theme'

const LIGHT = 'light'
const DARK = 'dark'

const theme = ref(LIGHT)

function canUseStorage() {
  return typeof window !== 'undefined' && Boolean(window.localStorage)
}

function readStoredTheme() {
  if (!canUseStorage()) return null
  try {
    return window.localStorage.getItem(THEME_STORAGE_KEY)
  } catch {
    return null
  }
}

export function normalizeTheme(value) {
  return value === DARK ? DARK : LIGHT
}

export function getTheme() {
  return theme.value
}

export function applyTheme(nextTheme, persist = false) {
  const normalized = normalizeTheme(nextTheme)
  theme.value = normalized
  if (typeof document !== 'undefined') document.documentElement.dataset.theme = normalized
  if (!persist || !canUseStorage()) return normalized
  try {
    window.localStorage.setItem(THEME_STORAGE_KEY, normalized)
  } catch {
    /* storage can be unavailable in private modes; the in-memory theme still applies */
  }
  return normalized
}

export function applyStoredTheme() {
  return applyTheme(readStoredTheme())
}

export function toggleTheme() {
  return applyTheme(theme.value === DARK ? LIGHT : DARK, true)
}

/**
 * Composable used by views. `useTheme()` intentionally does not apply the theme on
 * setup: boot-time application is handled once by `index.html` and `main.js`, so that
 * navigating between views and restoring a KeepAlive-cached view cannot re-trigger it.
 */
export function useTheme() {
  return { theme, applyTheme, applyStoredTheme, toggleTheme }
}
