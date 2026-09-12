<script setup>
import ProductCard from './ProductCard.vue'

defineOptions({ name: 'ProductGrid' })

defineProps({
  products: { type: Array, required: true },
  loading: { type: Boolean, default: false },
  error: { type: String, default: '' },
  emptyTitle: { type: String, default: '没有找到匹配的商品' },
  emptyHint: { type: String, default: '' },
})

defineEmits(['open', 'retry'])
</script>

<template>
  <p v-if="error" class="notice error" role="alert">
    <span class="notice-icon">!</span>
    <span>{{ error }}</span>
    <button type="button" @click="$emit('retry')">重试</button>
  </p>
  <div v-else-if="loading" class="product-grid" aria-label="正在加载商品">
    <div v-for="item in 8" :key="item" class="skeleton-card" aria-hidden="true">
      <div class="skeleton-image"></div>
      <div class="skeleton-line skeleton-title"></div>
      <div class="skeleton-line skeleton-price"></div>
    </div>
  </div>
  <div v-else-if="products.length === 0" class="notice empty-state">
    <span class="empty-icon">⌕</span>
    <strong>{{ emptyTitle }}</strong>
    <span v-if="emptyHint">{{ emptyHint }}</span>
  </div>
  <section v-else class="product-grid">
    <ProductCard v-for="product in products" :key="product.cluster_id" :product="product" @open="$emit('open', product)" />
  </section>
</template>

<style scoped>
.product-grid { display: grid; grid-template-columns: repeat(4, minmax(0, 1fr)); gap: 32px 16px; }
.notice { display: flex; align-items: center; justify-content: center; gap: 8px; min-height: 180px; padding: 32px 20px; border: 1px solid var(--color-border-soft); border-radius: 14px; color: var(--color-text-muted); font-size: var(--fs-14); }
.notice-icon { display: grid; width: 24px; height: 24px; place-items: center; border-radius: 50%; background: var(--color-error); color: var(--color-on-error); font-weight: 700; }
.notice button { padding: 0; border: 0; background: transparent; color: var(--color-error); font-size: var(--fs-14); text-decoration: underline; cursor: pointer; }
.empty-state { flex-direction: column; gap: 8px; }
.empty-state strong { color: var(--color-text-primary); font-size: var(--fs-16); font-weight: 600; }
.empty-icon { display: grid; width: 42px; height: 42px; margin-bottom: 4px; place-items: center; border-radius: 50%; background: var(--color-surface-strong); color: var(--color-text-muted); font-size: var(--fs-22); }
.skeleton-card { overflow: hidden; border-radius: 14px; }
.skeleton-image, .skeleton-line { background: linear-gradient(90deg, var(--color-surface-soft) 25%, var(--color-border-soft) 50%, var(--color-surface-soft) 75%); background-size: 200% 100%; animation: shimmer var(--duration-shimmer) infinite; }
.skeleton-image { aspect-ratio: 1 / 1; border-radius: 14px; }
.skeleton-line { height: 16px; margin: 16px 2px 0; border-radius: 8px; }
.skeleton-title { width: 76%; }
.skeleton-price { width: 38%; margin-top: 8px; }
@keyframes shimmer { to { background-position: -200% 0; } }
@media (max-width: 1128px) {
  .product-grid { grid-template-columns: repeat(3, minmax(0, 1fr)); }
}
@media (max-width: 744px) {
  .product-grid { grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 28px 12px; }
}
@media (prefers-reduced-motion: reduce) {
  .skeleton-image, .skeleton-line { animation-duration: .01ms; animation-iteration-count: 1; }
}
</style>
