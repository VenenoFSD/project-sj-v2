import './styles/theme.css'
import { createApp } from 'vue'
import App from './App.vue'
import router from './router'
import { applyStoredTheme } from './composables/useTheme'

// index.html applies the stored theme before first paint; this keeps the module the
// single source of truth for every other entry point (dev, tests, direct mounts).
applyStoredTheme()

createApp(App).use(router).mount('#app')
