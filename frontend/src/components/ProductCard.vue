<script setup>
import { ref } from 'vue'
import { Heart } from 'lucide-vue-next'
import PriceRow from './PriceRow.vue'
import { useFavorites } from '../composables/useFavorites'
import { normalizeImageUrl } from '../utils/format'

defineOptions({ name: 'ProductCard' })

const props = defineProps({
  product: { type: Object, required: true },
})

const emit = defineEmits(['open'])

const { isFavorited, isPending, toggleFavorite } = useFavorites()
const imageFailed = ref(false)

/**
 * 卡片整体是可点击的，回车打开详情。心形是卡片内部的按钮，它的回车/空格由按钮自己处理，
 * 所以这里只在事件确实落在卡片上时才打开抽屉，避免一次按键触发两个动作。
 */
function handleKeydown(event) {
  if (event.target !== event.currentTarget) return
  emit('open', props.product)
}
</script>

<template>
  <article class="product-card" tabindex="0" @click="emit('open', product)" @keydown.enter="handleKeydown">
    <div class="card-image-wrap">
      <img v-if="product.img && !imageFailed" :src="normalizeImageUrl(product.img)" :alt="product.title" loading="lazy" referrerpolicy="no-referrer" @error="imageFailed = true" />
      <div v-else class="image-placeholder"><span>暂无图片</span></div>
      <button
        class="favorite-button"
        :class="{ active: isFavorited(product.cluster_id) }"
        type="button"
        :aria-pressed="isFavorited(product.cluster_id)"
        :aria-label="isFavorited(product.cluster_id) ? `取消收藏 ${product.title}` : `收藏 ${product.title}`"
        :disabled="isPending(product.cluster_id)"
        @click.stop="toggleFavorite(product)"
      >
        <Heart :size="18" :stroke-width="1.8" :fill="isFavorited(product.cluster_id) ? 'currentColor' : 'none'" aria-hidden="true" />
      </button>
    </div>
    <div class="card-body">
      <h3>{{ product.title }}</h3>
      <PriceRow :price="product.price" :reference-price="product.reference_price" />
      <div class="card-meta"><span v-if="product.discount" class="tag">{{ product.discount }}</span></div>
    </div>
  </article>
</template>

<style scoped>
.product-card { overflow: hidden; border-radius: 14px; background: var(--color-surface); outline: 0; cursor: pointer; }
.product-card:hover, .product-card:focus-visible { box-shadow: var(--shadow-card); }
.product-card:focus-visible { box-shadow: 0 0 0 2px var(--color-focus), var(--shadow-card); }
.card-image-wrap { position: relative; aspect-ratio: 1 / 1; overflow: hidden; border-radius: 14px; background: var(--color-surface-soft); }
.card-image-wrap img { display: block; width: 100%; height: 100%; object-fit: contain; transition: transform var(--duration-base) var(--ease-standard); }
.product-card:hover .card-image-wrap img { transform: scale(1.03); }
.image-placeholder { display: grid; height: 100%; place-items: center; color: var(--color-text-disabled); font-size: var(--fs-12); }
/* DESIGN.md {component.icon-button-circle}：32px 圆形，压在图片右上角，12px 内边距；
   照片上再叠单一 shadow 层级保证可读性（同 {component.guest-favorite-badge} 的处理）。
   收藏后转 Rausch 填充 + 白色实心心形。点击后心形立即翻转，所以等待态只需要挡住重复点击。 */
.favorite-button { position: absolute; top: 12px; right: 12px; display: grid; width: 32px; height: 32px; padding: 0; place-items: center; border: 0; border-radius: 50%; background: var(--color-surface-strong); color: var(--color-text-primary); box-shadow: var(--shadow-card); cursor: pointer; transition: background var(--duration-fast) var(--ease-standard), color var(--duration-fast) var(--ease-standard); }
.favorite-button:hover, .favorite-button:focus-visible { background: var(--color-border); }
.favorite-button:focus-visible { outline: 2px solid var(--color-focus); outline-offset: 2px; }
.favorite-button.active { background: var(--color-accent); color: var(--color-on-accent); }
.favorite-button.active:hover, .favorite-button.active:focus-visible { background: var(--color-accent-hover); }
.favorite-button:disabled { cursor: not-allowed; }
.card-body { padding: 16px; }
.card-body h3 { display: -webkit-box; min-height: 40px; margin: 0 0 8px; overflow: hidden; color: var(--color-text-primary); font-size: var(--fs-16); font-weight: 600; line-height: 1.25; -webkit-line-clamp: 2; -webkit-box-orient: vertical; }
.card-meta { display: flex; align-items: center; justify-content: space-between; min-height: 28px; margin-top: 8px; }
.tag { display: inline-flex; align-items: center; padding: 4px 8px; border-radius: 9999px; background: var(--color-tag-surface); color: var(--color-error); font-size: var(--fs-11); font-weight: 600; line-height: 1.18; }
@media (max-width: 744px) {
  .card-body h3 { font-size: var(--fs-14); }
}
@media (prefers-reduced-motion: reduce) {
  .card-image-wrap img { transition-duration: .01ms; }
}
</style>
