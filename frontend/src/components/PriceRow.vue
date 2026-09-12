<script setup>
import { computed } from 'vue'
import { formatDiscount, formatPrice } from '../utils/format'

defineOptions({ name: 'PriceRow' })

const props = defineProps({
  price: { type: [Number, String], default: null },
  referencePrice: { type: [Number, String], default: null },
  // `card` 用于商品卡片（{typography.title-md}），`detail` 用于详情抽屉（{typography.display-lg}）。
  size: { type: String, default: 'card' },
})

const discount = computed(() => formatDiscount(props.price, props.referencePrice))
</script>

<template>
  <div class="price-row" :class="{ 'price-row-detail': size === 'detail' }">
    <strong>{{ formatPrice(price) }}</strong>
    <span v-if="referencePrice" class="reference">{{ formatPrice(referencePrice) }}</span>
    <span v-if="discount" class="price-discount">{{ discount }}</span>
  </div>
</template>

<style scoped>
.price-row { display: flex; align-items: center; gap: 8px; }
.price-row strong { color: var(--color-accent); font-size: var(--fs-16); font-weight: 600; line-height: 1.25; }
.price-row-detail strong { font-size: var(--fs-22); }
.reference { color: var(--color-text-disabled); font-size: var(--fs-12); text-decoration: line-through; }
.price-discount { display: inline-flex; align-items: center; padding: 4px 8px; border-radius: 9999px; background: var(--color-tag-surface); color: var(--color-accent); font-size: var(--fs-11); font-weight: 600; line-height: 1.18; }
</style>
