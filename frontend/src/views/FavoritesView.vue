<script setup>
import { computed, onMounted, ref } from 'vue'
import AppFooter from '../components/AppFooter.vue'
import AppHeader from '../components/AppHeader.vue'
import ProductDrawer from '../components/ProductDrawer.vue'
import ProductGrid from '../components/ProductGrid.vue'
import { useFavorites } from '../composables/useFavorites'

const { favorites, loading, error, loadFavorites } = useFavorites()
const selectedProduct = ref(null)

// 收藏页只展示收藏，没有搜索和筛选，所以列表就是收藏接口返回的顺序（最近收藏在前）。
const products = computed(() => favorites.value.map((item) => item.product).filter(Boolean))

onMounted(() => loadFavorites())
</script>

<template>
  <main class="page-shell">
    <AppHeader />

    <div class="results-heading">
      <div>
        <p class="section-kicker">SAVED ITEMS</p>
        <h2>我的收藏</h2>
      </div>
      <p v-if="products.length > 0" class="result-count">共 {{ products.length }} 件商品</p>
    </div>

    <ProductGrid :products="products" :loading="loading" :error="error" empty-title="还没有收藏的商品" empty-hint="在商品页点图片右上角的心形即可收藏" @open="selectedProduct = $event" @retry="loadFavorites(true)" />

    <ProductDrawer v-if="selectedProduct" :product="selectedProduct" :key="selectedProduct.cluster_id" @close="selectedProduct = null" />
    <AppFooter />
  </main>
</template>

<style scoped>
.page-shell { width: min(1280px, calc(100% - 64px)); margin: 0 auto; padding-bottom: 64px; }
.section-kicker { margin: 0 0 12px; color: var(--color-text-muted); font-size: var(--fs-11); font-weight: 700; letter-spacing: 1.2px; line-height: 1.3; text-transform: uppercase; }
.results-heading { display: flex; align-items: center; justify-content: space-between; margin: 40px 0 24px; }
.results-heading h2 { margin: 0; color: var(--color-text-primary); font-size: var(--fs-22); font-weight: 500; letter-spacing: -.44px; line-height: 1.18; }
.result-count { margin: 20px 0 0; color: var(--color-text-muted); font-size: var(--fs-14); }
@media (max-width: 1128px) {
  .page-shell { width: min(100% - 48px, 960px); }
}
@media (max-width: 744px) {
  .page-shell { width: min(100% - 32px, 560px); }
  .results-heading { margin-top: 32px; }
}
@media (max-width: 420px) {
  .page-shell { width: calc(100% - 24px); }
}
</style>
