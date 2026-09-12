<script setup>
import { computed, onMounted } from 'vue'
import { RouterLink, useRoute } from 'vue-router'
import { Heart, House, Moon, Sun } from 'lucide-vue-next'
import { applyStoredTheme, useTheme } from '../composables/useTheme'

defineOptions({ name: 'AppHeader' })

const route = useRoute()
const { theme, toggleTheme } = useTheme()

// `/` 与 `/products` 都是商品页，所以按路由名而不是路径判断当前 tab。
const tabs = [
  { label: '商品', to: '/products', icon: House, routes: ['home', 'products'] },
  { label: '收藏', to: '/favorites', icon: Heart, routes: ['favorites'] },
]

function isActive(tab) {
  return tab.routes.includes(route.name)
}

const themeLabel = computed(() => (theme.value === 'dark' ? '切换到浅色主题' : '切换到深色主题'))

onMounted(applyStoredTheme)
</script>

<template>
  <header class="top-nav">
    <RouterLink class="brand" to="/" aria-label="返回首页">
      <span class="brand-mark">S</span>
      <span class="brand-name">SJ Select</span>
    </RouterLink>
    <nav class="product-nav" aria-label="主导航">
      <RouterLink v-for="tab in tabs" :key="tab.to" class="product-tab" :class="{ active: isActive(tab) }" :to="tab.to" :aria-current="isActive(tab) ? 'page' : undefined">
        <span class="product-icon"><component :is="tab.icon" :size="20" :stroke-width="1.8" aria-hidden="true" /></span>
        <span>{{ tab.label }}</span>
      </RouterLink>
    </nav>
    <div class="nav-actions">
      <RouterLink class="admin-link" to="/backend">后台</RouterLink>
      <button class="theme-toggle" type="button" :aria-label="themeLabel" :title="themeLabel" @click="toggleTheme">
        <Sun v-if="theme === 'dark'" :size="18" :stroke-width="1.8" aria-hidden="true" />
        <Moon v-else :size="18" :stroke-width="1.8" aria-hidden="true" />
      </button>
    </div>
  </header>
</template>

<style scoped>
/* `position: relative` 是必需的：品牌和右侧操作区都相对导航条绝对定位。 */
.top-nav { position: relative; display: flex; height: 80px; align-items: center; justify-content: center; border-bottom: 1px solid var(--color-border-soft); }
.brand { position: absolute; left: 0; display: flex; align-items: center; gap: 8px; color: var(--color-text-primary); font-size: var(--fs-16); font-weight: 600; text-decoration: none; }
.brand-mark { display: grid; width: 32px; height: 32px; place-items: center; border-radius: 50%; background: var(--color-accent); color: var(--color-on-accent); font-size: var(--fs-20); font-weight: 600; }
.brand-name { letter-spacing: -.2px; }
.product-nav { display: flex; align-self: stretch; gap: 32px; }
.product-tab { position: relative; display: flex; align-items: center; gap: 8px; color: var(--color-text-muted); font-size: var(--fs-14); font-weight: 500; text-decoration: none; }
.product-tab:hover, .product-tab:focus-visible { color: var(--color-text-primary); }
.product-tab.active { color: var(--color-text-primary); font-weight: 600; }
.product-tab.active::after { position: absolute; right: 0; bottom: 0; left: 0; height: 2px; background: var(--color-text-primary); content: ""; }
.product-icon { display: grid; width: 24px; height: 24px; place-items: center; }
.nav-actions { position: absolute; right: 0; display: flex; align-items: center; }
.admin-link { margin-right: 16px; color: var(--color-text-muted); font-size: var(--fs-14); text-decoration: none; }
.admin-link:hover, .admin-link:focus-visible { color: var(--color-text-primary); text-decoration: underline; text-underline-offset: 4px; }
.theme-toggle { display: grid; width: 40px; height: 40px; padding: 0; place-items: center; border: 1px solid var(--color-border); border-radius: 50%; background: var(--color-surface); color: var(--color-text-primary); cursor: pointer; }
.theme-toggle:hover, .theme-toggle:focus-visible { background: var(--color-surface-strong); box-shadow: var(--shadow-card); }
/* 两个 tab 是进入收藏页的唯一入口，所以窄屏也保留（只收起品牌名），并收紧间距避免和右侧
   操作区重叠 —— DESIGN.md 的响应式表格已按此更新。 */
@media (max-width: 744px) {
  .top-nav { height: 64px; }
  .brand-name { display: none; }
  .product-nav { gap: 16px; }
}
@media (max-width: 420px) {
  .product-nav { gap: 12px; }
}
</style>
