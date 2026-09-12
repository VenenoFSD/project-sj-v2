<script setup>
import { computed, nextTick, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { LineChart } from 'echarts/charts'
import { GridComponent, TooltipComponent } from 'echarts/components'
import * as echarts from 'echarts/core'
import { CanvasRenderer } from 'echarts/renderers'
import { ArrowUpRight, Heart, X } from 'lucide-vue-next'
import { fetchProductDeals, fetchProductDetails, fetchProductHistory } from '../api/products'
import PriceRow from './PriceRow.vue'
import { useFavorites } from '../composables/useFavorites'
import { useTheme } from '../composables/useTheme'
import { normalizeImageUrl, parsePriceValue } from '../utils/format'

echarts.use([LineChart, GridComponent, TooltipComponent, CanvasRenderer])

defineOptions({ name: 'ProductDrawer' })

const props = defineProps({
  product: { type: Object, required: true },
})

const emit = defineEmits(['close'])

const { theme } = useTheme()
const { isFavorited, isPending, toggleFavorite } = useFavorites()

const drawerData = ref(null)
const drawerError = ref('')
const drawerLoading = ref(true)
const priceChartElement = ref(null)
const dealChartElement = ref(null)
let priceChart
let dealChart

const basic = computed(() => drawerData.value?.basic || props.product)

function getTrendData(items, valueKey, labelKey, reverse = true) {
  const data = items
    .map((item) => ({ value: parsePriceValue(item[valueKey]), label: item[labelKey] || '' }))
    .filter((item) => Number.isFinite(item.value))
  return reverse ? data.reverse() : data
}

function formatTrendTime(value) {
  const text = String(value || '').trim()
  const match = text.match(/^(\d{4}[-/]\d{2}[-/]\d{2})[T\s]+(\d{2}:\d{2}:\d{2})/)
  if (match) return `${match[1].replace(/\//g, '-')} ${match[2]}`
  return text.replace('T', ' ')
}

function formatTrendLabel(value) {
  const text = formatTrendTime(value)
  return text.length > 16 ? text.slice(5, 16) : text
}

function getThemeColor(name) {
  return getComputedStyle(document.documentElement).getPropertyValue(name).trim()
}

function renderTrendChart(element, data, color, seriesName) {
  if (!element || !data.length) return null
  const chart = echarts.getInstanceByDom(element) || echarts.init(element)
  chart.setOption({
    animationDuration: 350,
    grid: { top: 18, right: 18, bottom: 34, left: 46 },
    tooltip: {
      trigger: 'axis',
      confine: true,
      backgroundColor: getThemeColor('--color-tooltip-surface'),
      borderColor: getThemeColor('--color-border'),
      borderWidth: 1,
      textStyle: { color: getThemeColor('--color-tooltip-text') },
      formatter: (params) => {
        const point = params[0]
        return `${formatTrendTime(point.axisValue)}<br/>${point.marker}${point.seriesName}：¥${Number(point.value).toFixed(2)}`
      },
    },
    xAxis: {
      type: 'category',
      boundaryGap: false,
      data: data.map((item) => item.label),
      axisLabel: { color: getThemeColor('--color-chart-label'), hideOverlap: true, formatter: formatTrendLabel },
      axisLine: { lineStyle: { color: getThemeColor('--color-chart-axis') } },
      axisTick: { show: false },
    },
    yAxis: {
      type: 'value',
      scale: true,
      axisLabel: { color: getThemeColor('--color-chart-label'), formatter: (value) => `¥${Number(value).toFixed(0)}` },
      axisLine: { show: false },
      axisTick: { show: false },
      splitLine: { lineStyle: { color: getThemeColor('--color-chart-grid') } },
    },
    series: [{
      name: seriesName,
      type: 'line',
      data: data.map((item) => item.value),
      smooth: true,
      showSymbol: data.length <= 40,
      symbol: 'circle',
      symbolSize: 7,
      lineStyle: { color, width: 3 },
      itemStyle: { color, borderColor: getThemeColor('--color-chart-surface'), borderWidth: 2 },
      areaStyle: { color, opacity: 0.12 },
      emphasis: { focus: 'series' },
    }],
  })
  return chart
}

const priceTrendData = computed(() => getTrendData(drawerData.value?.history || [], 'price', 'captured_at'))
const dealTrendData = computed(() => getTrendData(drawerData.value?.deals || [], 'deal_price', 'deal_time', false))

function renderCharts() {
  nextTick(() => {
    disposeCharts()
    priceChart = renderTrendChart(priceChartElement.value, priceTrendData.value, getThemeColor('--color-chart-price'), '挂牌价')
    dealChart = renderTrendChart(dealChartElement.value, dealTrendData.value, getThemeColor('--color-chart-deal'), '成交价')
  })
}

function disposeCharts() {
  if (priceChart) {
    priceChart.dispose()
    priceChart = null
  }
  if (dealChart) {
    dealChart.dispose()
    dealChart = null
  }
}

function resizeCharts() {
  priceChart?.resize()
  dealChart?.resize()
}

// 图表颜色取自主题变量，所以主题一变就重绘，不依赖是谁触发的切换。
watch(theme, renderCharts)

onMounted(() => {
  document.body.style.overflow = 'hidden'
  window.addEventListener('resize', resizeCharts)
  Promise.allSettled([
    fetchProductDetails(props.product.cluster_id),
    fetchProductHistory(props.product.cluster_id),
    fetchProductDeals(props.product.cluster_id),
  ]).then(([details, history, deals]) => {
    drawerData.value = {
      basic: props.product,
      details: details.status === 'fulfilled' ? (details.value.detail || details.value) : null,
      history: history.status === 'fulfilled' ? history.value.items || [] : [],
      deals: deals.status === 'fulfilled' ? deals.value.items || [] : [],
    }
    if ([details, history, deals].every((result) => result.status === 'rejected')) drawerError.value = '详情暂时无法加载，请稍后重试'
  }).finally(() => {
    drawerLoading.value = false
    renderCharts()
  })
})

onBeforeUnmount(() => {
  window.removeEventListener('resize', resizeCharts)
  disposeCharts()
  document.body.style.overflow = ''
})
</script>

<template>
  <div class="drawer-backdrop" @click="emit('close')">
    <aside class="drawer" role="dialog" aria-modal="true" aria-label="商品详情" @click.stop>
      <div class="drawer-actions">
        <button
          class="drawer-icon-button favorite-button"
          :class="{ active: isFavorited(product.cluster_id) }"
          type="button"
          :aria-pressed="isFavorited(product.cluster_id)"
          :aria-label="isFavorited(product.cluster_id) ? `取消收藏 ${product.title}` : `收藏 ${product.title}`"
          :disabled="isPending(product.cluster_id)"
          @click="toggleFavorite(product)"
        >
          <Heart :size="18" :stroke-width="1.8" :fill="isFavorited(product.cluster_id) ? 'currentColor' : 'none'" aria-hidden="true" />
        </button>
        <button class="drawer-icon-button drawer-close" type="button" aria-label="关闭详情" @click="emit('close')"><X :size="20" :stroke-width="1.8" aria-hidden="true" /></button>
      </div>
      <div v-if="drawerLoading" class="drawer-state"><span class="loader"></span><span>正在加载商品详情…</span></div>
      <template v-else>
        <div class="drawer-image"><img v-if="product.img" :src="normalizeImageUrl(product.img)" :alt="product.title" referrerpolicy="no-referrer" /></div>
        <p class="drawer-kicker">PRODUCT DETAILS</p>
        <h2>{{ product.title }}</h2>
        <PriceRow :price="basic.price" :reference-price="basic.reference_price" size="detail" />
        <div class="tag-row"><span v-if="product.discount" class="tag">{{ product.discount }}</span><span class="tracked-tag">价格追踪中</span></div>
        <p v-if="drawerError" class="drawer-error" role="alert">{{ drawerError }}</p>
        <section v-if="drawerData?.details" class="detail-section"><div class="section-title"><h3>详情信息</h3><span>OVERVIEW</span></div><div class="detail-facts"><p><span>当前价</span><strong>{{ drawerData.details.price_tag?.firstPrice ? `${drawerData.details.price_tag.firstPriceSymbol || '¥'}${drawerData.details.price_tag.firstPrice}` : '暂无' }}</strong></p><p><span>参考价</span><strong>{{ drawerData.details.price_tag?.price ? `${drawerData.details.price_tag.priceSymbol || '¥'}${drawerData.details.price_tag.price}` : '暂无' }}</strong></p><p><span>最低价</span><strong>{{ drawerData.details.lowest_price || '暂无' }}</strong></p><p><span>最近成交价</span><strong>{{ drawerData.details.latest_deal_price || '暂无' }}</strong></p></div><div v-if="drawerData.details.attributes?.length" class="attribute-list"><div v-for="item in drawerData.details.attributes" :key="item.name"><span>{{ item.name }}</span><strong>{{ item.value }}</strong></div></div></section>
        <section class="detail-section"><div class="section-title"><h3>价格历史</h3><span>{{ drawerData?.history?.length || 0 }} 条记录</span></div><div v-if="priceTrendData.length" ref="priceChartElement" class="trend-chart" role="img" aria-label="价格历史趋势"></div><p v-else class="muted">暂无价格历史</p></section>
        <section class="detail-section"><div class="section-title"><h3>成交记录</h3><span>{{ drawerData?.deals?.length || 0 }} 条记录</span></div><div v-if="dealTrendData.length" ref="dealChartElement" class="trend-chart" role="img" aria-label="成交记录趋势"></div><p v-else class="muted">暂无成交记录</p></section>
        <a v-if="product.url" class="external-link" :href="product.url" target="_blank" rel="noopener">查看商品页面 <ArrowUpRight :size="16" :stroke-width="1.8" aria-hidden="true" /></a>
      </template>
    </aside>
  </div>
</template>

<style scoped>
.drawer-backdrop { position: fixed; z-index: 10; inset: 0; background: var(--color-scrim); }
.drawer { position: absolute; top: 0; right: 0; width: min(720px, 100%); height: 100%; padding: 32px 40px 48px; overflow-y: auto; background: var(--color-surface); box-shadow: var(--shadow-drawer); animation: slide-in var(--duration-drawer) var(--ease-entrance); }
/* 心形与关闭按钮成组贴在右上角，标题的右内边距按两个 40px 圆钮 + 间距预留。 */
.drawer-actions { position: absolute; top: 20px; right: 24px; display: flex; gap: 8px; }
.drawer-icon-button { display: grid; width: 40px; height: 40px; padding: 0; place-items: center; border: 0; border-radius: 50%; background: var(--color-surface-strong); color: var(--color-text-primary); cursor: pointer; transition: background var(--duration-fast) var(--ease-standard), color var(--duration-fast) var(--ease-standard); }
.drawer-icon-button:hover, .drawer-icon-button:focus-visible { background: var(--color-border); }
.drawer-icon-button:focus-visible { outline: 2px solid var(--color-focus); outline-offset: 2px; }
.favorite-button.active { background: var(--color-accent); color: var(--color-on-accent); }
.favorite-button.active:hover, .favorite-button.active:focus-visible { background: var(--color-accent-hover); }
.drawer-icon-button:disabled { cursor: not-allowed; }
.drawer-image { aspect-ratio: 1 / .72; margin-bottom: 24px; overflow: hidden; border-radius: 14px; background: var(--color-surface-soft); }
.drawer-image img { display: block; width: 100%; height: 100%; object-fit: contain; }
.drawer-kicker { margin-bottom: 8px; color: var(--color-text-muted); font-size: var(--fs-11); font-weight: 700; letter-spacing: 1.2px; line-height: 1.3; text-transform: uppercase; }
.drawer h2 { max-width: 580px; margin: 0 96px 16px 0; color: var(--color-text-primary); font-size: var(--fs-22); font-weight: 500; letter-spacing: -.44px; line-height: 1.18; }
.tag-row { display: flex; gap: 8px; min-height: 28px; margin-top: 16px; }
.tag, .tracked-tag { display: inline-flex; align-items: center; padding: 4px 8px; border-radius: 9999px; background: var(--color-tag-surface); color: var(--color-error); font-size: var(--fs-11); font-weight: 600; line-height: 1.18; }
.tracked-tag { background: var(--color-surface-soft); color: var(--color-text-muted); }
.drawer-error { margin: 24px 0 0; padding: 12px 16px; border-radius: 8px; background: var(--color-error-surface); color: var(--color-error); font-size: var(--fs-13); }
.detail-section { margin-top: 32px; padding-top: 24px; border-top: 1px solid var(--color-border-soft); }
.section-title { display: flex; align-items: center; justify-content: space-between; gap: 16px; margin-bottom: 16px; }
.section-title h3 { margin: 0; color: var(--color-text-primary); font-size: var(--fs-20); font-weight: 600; line-height: 1.2; }
.section-title span { color: var(--color-text-disabled); font-size: var(--fs-12); }
.detail-facts { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 12px 24px; }
.detail-facts p { display: flex; align-items: baseline; justify-content: space-between; gap: 12px; margin: 0; padding: 12px 0; border-bottom: 1px solid var(--color-surface-strong); color: var(--color-text-muted); font-size: var(--fs-14); }
.detail-facts strong { color: var(--color-text-primary); font-weight: 500; text-align: right; }
.detail-section p.muted { margin: 0; color: var(--color-text-disabled); font-size: var(--fs-14); }
.muted { color: var(--color-text-disabled) !important; }
.attribute-list { display: grid; gap: 8px; margin-top: 16px; }
.attribute-list div { display: flex; align-items: center; justify-content: space-between; gap: 12px; padding: 12px; border-radius: 8px; background: var(--color-surface-soft); font-size: var(--fs-13); }
.attribute-list span { color: var(--color-text-muted); }
.attribute-list strong { color: var(--color-text-primary); font-weight: 500; }
.trend-chart { width: 100%; height: 260px; }
.external-link { display: inline-flex; align-items: center; gap: 4px; margin-top: 32px; color: var(--color-text-primary); font-size: var(--fs-14); text-underline-offset: 4px; }
.external-link:hover, .external-link:focus-visible { color: var(--color-text-primary); text-decoration: underline; }
.drawer-state { display: flex; min-height: 360px; align-items: center; justify-content: center; gap: 12px; color: var(--color-text-muted); font-size: var(--fs-14); }
.loader { width: 18px; height: 18px; border: 2px solid var(--color-accent-disabled); border-top-color: var(--color-accent); border-radius: 50%; animation: spin var(--duration-spin) linear infinite; }
@keyframes slide-in { from { transform: translateX(100%); } to { transform: translateX(0); } }
@keyframes spin { to { transform: rotate(360deg); } }
@media (max-width: 744px) {
  .drawer { padding: 24px 20px 40px; }
  .drawer-image { margin-top: 32px; }
  .detail-facts { gap: 0 16px; }
}
@media (prefers-reduced-motion: reduce) {
  .drawer { animation-duration: .01ms; }
  .loader { animation-duration: .01ms; animation-iteration-count: 1; }
}
</style>
