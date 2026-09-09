<script setup>
import { computed, nextTick, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { LineChart } from 'echarts/charts'
import { GridComponent, TooltipComponent } from 'echarts/components'
import * as echarts from 'echarts/core'
import { CanvasRenderer } from 'echarts/renderers'
import { ArrowUpRight, ChevronLeft, ChevronRight, Heart, House, Moon, Search, Sparkles, Sun, X } from 'lucide-vue-next'
import { fetchCatalog } from '../api/catalog'
import { fetchProductDeals, fetchProductDetails, fetchProductHistory, fetchProducts } from '../api/products'
import BaseSelect from '../components/BaseSelect.vue'

echarts.use([LineChart, GridComponent, TooltipComponent, CanvasRenderer])

const products = ref([])
const categories = ref([])
const category = ref('')
const sort = ref('')
const search = ref('')
const submittedSearch = ref('')
const page = ref(1)
const pageSize = 24
const loading = ref(false)
const error = ref('')
const imageErrors = ref(new Set())
const total = ref(0)
const selectedProduct = ref(null)
const drawerLoading = ref(false)
const drawerError = ref('')
const drawerData = ref(null)
const priceChartElement = ref(null)
const dealChartElement = ref(null)
const theme = ref('light')
const themeStorageKey = 'sj-select-theme'
let priceChart
let dealChart

const sortOptions = [
  { value: '', label: '默认' },
  { value: 'discount', label: '折扣' },
  { value: 'price', label: '价格' },
]
const categoryOptions = computed(() => [
  { value: '', label: '全部' },
  ...categories.value.map((item) => ({ value: String(item.item_id), label: item.name || String(item.item_id) })),
])

const totalPages = computed(() => Math.max(1, Math.ceil(total.value / pageSize)))
const pageNumbers = computed(() => {
  const start = Math.max(1, Math.min(page.value - 2, totalPages.value - 4))
  return Array.from({ length: Math.min(5, totalPages.value) }, (_, index) => start + index)
})

async function loadProducts() {
  loading.value = true
  error.value = ''
  try {
    const data = await fetchProducts({ category: category.value, search: submittedSearch.value, sort: sort.value, limit: pageSize, offset: (page.value - 1) * pageSize })
    products.value = data.items || []
    total.value = data.total || 0
  } catch (err) {
    error.value = err.message || '加载商品失败，请稍后重试'
  } finally {
    loading.value = false
  }
}

function resetAndLoad() {
  page.value = 1
  loadProducts()
}

function submitSearch() {
  submittedSearch.value = search.value.trim()
  resetAndLoad()
}

function openProduct(product) {
  disposeCharts()
  selectedProduct.value = product
  drawerData.value = null
  drawerError.value = ''
  drawerLoading.value = true
  document.body.style.overflow = 'hidden'
  Promise.allSettled([
    fetchProductDetails(product.cluster_id),
    fetchProductHistory(product.cluster_id),
    fetchProductDeals(product.cluster_id),
  ]).then(([details, history, deals]) => {
    drawerData.value = {
      basic: product,
      details: details.status === 'fulfilled' ? (details.value.detail || details.value) : null,
      history: history.status === 'fulfilled' ? history.value.items || [] : [],
      deals: deals.status === 'fulfilled' ? deals.value.items || [] : [],
    }
    if ([details, history, deals].every((result) => result.status === 'rejected')) drawerError.value = '详情暂时无法加载，请稍后重试'
  }).finally(() => {
    drawerLoading.value = false
    renderCharts()
  })
}

function closeProduct() {
  disposeCharts()
  selectedProduct.value = null
  document.body.style.overflow = ''
}

function formatPrice(value) {
  return value === null || value === undefined ? '暂无价格' : `¥${Number(value).toFixed(2)}`
}

function parsePriceValue(value) {
  if (value === null || value === undefined) return null
  const match = String(value).replace(/,/g, '').match(/-?\d+(?:\.\d+)?/)
  return match ? Number(match[0]) : null
}

function formatDiscount(currentPrice, referencePrice) {
  const current = parsePriceValue(currentPrice)
  const reference = parsePriceValue(referencePrice)
  if (!Number.isFinite(current) || !Number.isFinite(reference) || current < 0 || reference <= 0 || current >= reference) return ''
  const discount = Math.round((current / reference) * 100) / 10
  return `${discount.toFixed(1).replace(/\.0$/, '')}折`
}

function parseTrendValue(value) {
  if (value === null || value === undefined) return null
  const match = String(value).replace(/,/g, '').match(/-?\d+(?:\.\d+)?/)
  return match ? Number(match[0]) : null
}

function getTrendData(items, valueKey, labelKey, reverse = true) {
  const data = items
    .map((item) => ({ value: parseTrendValue(item[valueKey]), label: item[labelKey] || '' }))
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

function applyTheme(nextTheme, persist = false) {
  theme.value = nextTheme
  document.documentElement.dataset.theme = nextTheme
  if (persist) {
    try {
      window.localStorage.setItem(themeStorageKey, nextTheme)
    } catch {
      return
    }
  }
}

function initializeTheme() {
  let storedTheme = 'light'
  try {
    storedTheme = window.localStorage.getItem(themeStorageKey) || 'light'
  } catch {
    storedTheme = 'light'
  }
  applyTheme(storedTheme === 'dark' ? 'dark' : 'light')
}

function toggleTheme() {
  applyTheme(theme.value === 'dark' ? 'light' : 'dark', true)
  renderCharts()
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

function normalizeImageUrl(value) {
  if (!value) return ''
  if (value.startsWith('//')) return `https:${value}`
  if (value.startsWith('http://')) return value.replace('http://', 'https://')
  return value
}

function imageFailed(clusterId) {
  imageErrors.value = new Set([...imageErrors.value, clusterId])
}

async function loadCategories() {
  try {
    const data = await fetchCatalog('category')
    categories.value = data.items || []
  } catch {
    categories.value = []
  }
}

onMounted(() => {
  initializeTheme()
  loadProducts()
  loadCategories()
  window.addEventListener('resize', resizeCharts)
})
onBeforeUnmount(() => {
  window.removeEventListener('resize', resizeCharts)
  disposeCharts()
  document.body.style.overflow = ''
})
watch([category, sort], resetAndLoad)
</script>

<template>
  <main class="page-shell">
    <header class="top-nav">
      <a class="brand" href="/" aria-label="返回首页">
        <span class="brand-mark">S</span>
        <span class="brand-name">SJ Select</span>
      </a>
      <nav class="product-nav" aria-label="主导航">
        <a class="product-tab active" href="#products"><span class="product-icon"><House :size="20" :stroke-width="1.8" aria-hidden="true" /></span><span>商品</span></a>
        <a class="product-tab" href="#products"><span class="product-icon"><Sparkles :size="20" :stroke-width="1.8" aria-hidden="true" /></span><span>精选</span><span class="new-tag">NEW</span></a>
        <a class="product-tab" href="#products"><span class="product-icon"><Heart :size="20" :stroke-width="1.8" aria-hidden="true" /></span><span>关注</span><span class="new-tag">NEW</span></a>
      </nav>
      <div class="nav-actions">
        <RouterLink class="admin-link" to="/backend">后台</RouterLink>
        <button class="theme-toggle" type="button" :aria-label="theme === 'dark' ? '切换到浅色主题' : '切换到深色主题'" :title="theme === 'dark' ? '切换到浅色主题' : '切换到深色主题'" @click="toggleTheme">
          <Sun v-if="theme === 'dark'" :size="18" :stroke-width="1.8" aria-hidden="true" />
          <Moon v-else :size="18" :stroke-width="1.8" aria-hidden="true" />
        </button>
      </div>
    </header>

    <section class="hero" aria-labelledby="page-title">
      <h1 id="page-title">发现值得关注的商品</h1>
    </section>

    <div class="search-filter-row">
      <section id="products" class="search-section" aria-label="商品筛选">
        <span class="filter-label">搜索商品</span>
        <form class="search-bar" @submit.prevent="submitSearch">
          <div class="search-field search-field-main">
            <input v-model="search" aria-label="搜索商品名称" placeholder="输入商品名称" />
          </div>
          <button class="search-orb" type="submit" aria-label="搜索" :disabled="loading"><Search :size="20" :stroke-width="2.2" aria-hidden="true" /></button>
        </form>
      </section>

      <div class="filter-row" aria-label="商品筛选">
        <BaseSelect v-model="category" class="category-filter" label="分类" :options="categoryOptions" />
        <div class="sort-filter">
          <span id="sort-label" class="filter-label">排序</span>
          <div class="sort-options" role="group" aria-labelledby="sort-label">
            <button v-for="option in sortOptions" :key="option.value" class="sort-option" :class="{ active: sort === option.value }" type="button" :disabled="loading" @click="sort = option.value">{{ option.label }}</button>
          </div>
        </div>
      </div>
    </div>

    <div class="results-heading">
      <div>
        <p class="section-kicker">LATEST ARRIVALS</p>
        <h2>热门商品</h2>
      </div>
      <p v-if="total > 0" class="result-count">共 {{ total }} 件商品</p>
    </div>

    <p v-if="error" class="notice error" role="alert">
      <span class="notice-icon">!</span>
      <span>{{ error }}</span>
      <button type="button" @click="loadProducts">重试</button>
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
      <strong>没有找到匹配的商品</strong>
      <span>试试其他关键词或切换商品分类</span>
    </div>

    <section v-else class="product-grid">
      <article v-for="product in products" :key="product.cluster_id" class="product-card" tabindex="0" @click="openProduct(product)" @keydown.enter="openProduct(product)">
        <div class="card-image-wrap">
          <img v-if="product.img && !imageErrors.has(product.cluster_id)" :src="normalizeImageUrl(product.img)" :alt="product.title" loading="lazy" referrerpolicy="no-referrer" @error="imageFailed(product.cluster_id)" />
          <div v-else class="image-placeholder"><span>暂无图片</span></div>
        </div>
        <div class="card-body">
          <h3>{{ product.title }}</h3>
          <div class="price-row"><strong>{{ formatPrice(product.price) }}</strong><span v-if="product.reference_price" class="reference">¥{{ Number(product.reference_price).toFixed(2) }}</span><span v-if="formatDiscount(product.price, product.reference_price)" class="price-discount">{{ formatDiscount(product.price, product.reference_price) }}</span></div>
          <div class="card-meta"><span v-if="product.discount" class="tag">{{ product.discount }}</span></div>
        </div>
      </article>
    </section>

    <nav v-if="total > 0" class="pagination" aria-label="分页">
      <button class="pagination-arrow" type="button" :disabled="page === 1 || loading" aria-label="上一页" @click="page--; loadProducts()"><ChevronLeft :size="18" :stroke-width="1.8" aria-hidden="true" /></button>
      <button v-for="number in pageNumbers" :key="number" type="button" :class="{ active: number === page }" :disabled="loading" @click="page = number; loadProducts()">{{ number }}</button>
      <span class="page-total">{{ page }} / {{ totalPages }}</span>
      <button class="pagination-arrow" type="button" :disabled="page === totalPages || loading" aria-label="下一页" @click="page++; loadProducts()"><ChevronRight :size="18" :stroke-width="1.8" aria-hidden="true" /></button>
    </nav>

    <div v-if="selectedProduct" class="drawer-backdrop" @click="closeProduct">
      <aside class="drawer" role="dialog" aria-modal="true" aria-label="商品详情" @click.stop>
        <button class="drawer-close" type="button" aria-label="关闭详情" @click="closeProduct"><X :size="20" :stroke-width="1.8" aria-hidden="true" /></button>
        <div v-if="drawerLoading" class="drawer-state"><span class="loader"></span><span>正在加载商品详情…</span></div>
        <template v-else>
          <div class="drawer-image"><img v-if="selectedProduct.img" :src="normalizeImageUrl(selectedProduct.img)" :alt="selectedProduct.title" referrerpolicy="no-referrer" /></div>
          <p class="drawer-kicker">PRODUCT DETAILS</p>
          <h2>{{ selectedProduct.title }}</h2>
          <div class="drawer-price-row"><strong>{{ formatPrice((drawerData?.basic || selectedProduct).price) }}</strong><span v-if="(drawerData?.basic || selectedProduct).reference_price" class="reference">¥{{ Number((drawerData?.basic || selectedProduct).reference_price).toFixed(2) }}</span><span v-if="formatDiscount((drawerData?.basic || selectedProduct).price, (drawerData?.basic || selectedProduct).reference_price)" class="price-discount">{{ formatDiscount((drawerData?.basic || selectedProduct).price, (drawerData?.basic || selectedProduct).reference_price) }}</span></div>
          <div class="tag-row"><span v-if="selectedProduct.discount" class="tag">{{ selectedProduct.discount }}</span><span class="tracked-tag">价格追踪中</span></div>
          <p v-if="drawerError" class="drawer-error" role="alert">{{ drawerError }}</p>
          <section v-if="drawerData?.details" class="detail-section"><div class="section-title"><h3>详情信息</h3><span>OVERVIEW</span></div><div class="detail-facts"><p><span>当前价</span><strong>{{ drawerData.details.price_tag?.firstPrice ? `${drawerData.details.price_tag.firstPriceSymbol || '¥'}${drawerData.details.price_tag.firstPrice}` : '暂无' }}</strong></p><p><span>参考价</span><strong>{{ drawerData.details.price_tag?.price ? `${drawerData.details.price_tag.priceSymbol || '¥'}${drawerData.details.price_tag.price}` : '暂无' }}</strong></p><p><span>最低价</span><strong>{{ drawerData.details.lowest_price || '暂无' }}</strong></p><p><span>最近成交价</span><strong>{{ drawerData.details.latest_deal_price || '暂无' }}</strong></p></div><div v-if="drawerData.details.attributes?.length" class="attribute-list"><div v-for="item in drawerData.details.attributes" :key="item.name"><span>{{ item.name }}</span><strong>{{ item.value }}</strong></div></div></section>
          <section class="detail-section"><div class="section-title"><h3>价格历史</h3><span>{{ drawerData?.history?.length || 0 }} 条记录</span></div><div v-if="priceTrendData.length" ref="priceChartElement" class="trend-chart" role="img" aria-label="价格历史趋势"></div><p v-else class="muted">暂无价格历史</p></section>
          <section class="detail-section"><div class="section-title"><h3>成交记录</h3><span>{{ drawerData?.deals?.length || 0 }} 条记录</span></div><div v-if="dealTrendData.length" ref="dealChartElement" class="trend-chart" role="img" aria-label="成交记录趋势"></div><p v-else class="muted">暂无成交记录</p></section>
          <a v-if="selectedProduct.url" class="external-link" :href="selectedProduct.url" target="_blank" rel="noopener">查看商品页面 <ArrowUpRight :size="16" :stroke-width="1.8" aria-hidden="true" /></a>
        </template>
      </aside>
    </div>
  </main>
</template>

<style scoped>
:global(*) { box-sizing: border-box; }
:global(html) { scroll-behavior: smooth; }
:global(:root) {
  color-scheme: light;
  --color-canvas: #fff;
  --color-surface: #fff;
  --color-surface-soft: #f7f7f7;
  --color-surface-strong: #f2f2f2;
  --color-text-primary: #222;
  --color-text-secondary: #3f3f3f;
  --color-text-muted: #6a6a6a;
  --color-text-disabled: #929292;
  --color-border: #ddd;
  --color-border-soft: #ebebeb;
  --color-border-strong: #c1c1c1;
  --color-accent: #ff385c;
  --color-accent-hover: #e00b41;
  --color-accent-disabled: #ffd1da;
  --color-on-accent: #fff;
  --color-on-accent-disabled: #fff;
  --color-error: #c13515;
  --color-on-error: #fff;
  --color-error-hover: #b32505;
  --color-error-surface: #fff4f2;
  --color-tag-surface: #fff0f2;
  --color-tooltip-surface: #fff;
  --color-tooltip-text: #222;
  --color-focus: #222;
  --color-scrim: rgba(0, 0, 0, .5);
  --shadow-card: rgba(0, 0, 0, .02) 0 0 0 1px, rgba(0, 0, 0, .04) 0 2px 6px, rgba(0, 0, 0, .1) 0 4px 8px;
  --shadow-drawer: -8px 0 20px rgba(0, 0, 0, .08);
  --color-chart-label: #94a3b8;
  --color-chart-axis: #e9edf4;
  --color-chart-grid: #edf0f5;
  --color-chart-surface: #fff;
  --color-chart-price: #dc4d5d;
  --color-chart-deal: #536da4;
}
:global(:root[data-theme="dark"]) {
  color-scheme: dark;
  --color-canvas: #151515;
  --color-surface: #1d1d1d;
  --color-surface-soft: #242424;
  --color-surface-strong: #2c2c2c;
  --color-text-primary: #f5f5f5;
  --color-text-secondary: #dedede;
  --color-text-muted: #ababab;
  --color-text-disabled: #777;
  --color-border: #3b3b3b;
  --color-border-soft: #2d2d2d;
  --color-border-strong: #5a5a5a;
  --color-accent: #ff5470;
  --color-accent-hover: #ff7188;
  --color-accent-disabled: #713847;
  --color-on-accent: #fff;
  --color-on-accent-disabled: #fff;
  --color-error: #ff8a65;
  --color-on-error: #151515;
  --color-error-hover: #ffab91;
  --color-error-surface: #3a211d;
  --color-tag-surface: #3a2028;
  --color-tooltip-surface: #2c2c2c;
  --color-tooltip-text: #f5f5f5;
  --color-focus: #fff;
  --color-scrim: rgba(0, 0, 0, .68);
  --shadow-card: rgba(255, 255, 255, .07) 0 0 0 1px, rgba(0, 0, 0, .28) 0 4px 12px;
  --shadow-drawer: -8px 0 20px rgba(0, 0, 0, .28);
  --color-chart-label: #aeb4c0;
  --color-chart-axis: #3a414d;
  --color-chart-grid: #343a45;
  --color-chart-surface: #1d1d1d;
  --color-chart-price: #ff6b83;
  --color-chart-deal: #9eb7e8;
}
:global(body) { margin: 0; background: var(--color-canvas); color: var(--color-text-primary); font-family: "Airbnb Cereal VF", Circular, Inter, -apple-system, system-ui, Roboto, "Helvetica Neue", sans-serif; }
:global(button), :global(input), :global(select) { font: inherit; }
:global(button), :global(a) { -webkit-tap-highlight-color: transparent; }
.page-shell { width: min(1280px, calc(100% - 64px)); margin: 0 auto; padding-bottom: 64px; }
.top-nav { display: flex; align-items: center; justify-content: space-between; height: 80px; border-bottom: 1px solid var(--color-border-soft); }
.brand, .product-tab, .search-bar, .search-field, .filter-row, .results-heading, .price-row, .card-meta, .pagination, .section-title, .drawer-price-row { display: flex; align-items: center; }
.top-nav { position: relative; justify-content: center; }
.brand { position: absolute; left: 0; gap: 9px; color: var(--color-text-primary); font-size: 16px; font-weight: 600; text-decoration: none; }
.brand-mark { display: grid; width: 32px; height: 32px; place-items: center; border-radius: 50%; background: var(--color-accent); color: var(--color-on-accent); font-size: 18px; font-weight: 700; }
.brand-name { letter-spacing: -.2px; }
.product-nav { display: flex; align-self: stretch; gap: 34px; }
.product-tab { position: relative; gap: 7px; color: var(--color-text-muted); font-size: 14px; font-weight: 500; text-decoration: none; }
.product-tab:hover, .product-tab:focus-visible { color: var(--color-text-primary); }
.product-tab.active { color: var(--color-text-primary); font-weight: 600; }
.product-tab.active::after { position: absolute; right: 0; bottom: 0; left: 0; height: 2px; background: var(--color-text-primary); content: ""; }
.product-icon { display: grid; width: 24px; height: 24px; place-items: center; }
.new-tag { position: absolute; top: 16px; right: -23px; padding: 2px 6px; border-radius: 9999px; background: var(--color-surface-strong); color: var(--color-text-primary); font-size: 8px; font-weight: 700; letter-spacing: .32px; line-height: 1.25; }
.nav-actions { position: absolute; right: 0; display: flex; align-items: center; }
.admin-link { margin-right: 16px; color: var(--color-text-muted); font-size: 14px; text-decoration: none; }
.admin-link:hover, .admin-link:focus-visible { color: var(--color-text-primary); text-decoration: underline; text-underline-offset: 4px; }
.theme-toggle { display: grid; width: 40px; height: 40px; padding: 0; place-items: center; border: 1px solid var(--color-border); border-radius: 50%; background: var(--color-surface); color: var(--color-text-primary); cursor: pointer; }
.theme-toggle:hover, .theme-toggle:focus-visible { background: var(--color-surface-strong); box-shadow: var(--shadow-card); }
.hero { padding: 64px 0 40px; text-align: center; }
.section-kicker, .drawer-kicker { margin: 0 0 12px; color: var(--color-accent); font-size: 11px; font-weight: 700; letter-spacing: 1.2px; line-height: 1.3; }
.hero h1 { margin: 0; color: var(--color-text-primary); font-size: clamp(24px, 3vw, 28px); font-weight: 700; letter-spacing: 0; line-height: 1.43; }
.search-filter-row { display: flex; align-items: center; gap: 24px; width: 100%; margin: 0 auto; }
.search-section { display: flex; flex: 1 1 auto; min-width: 0; flex-direction: column; align-items: stretch; gap: 8px; }
.search-bar { flex: 0 0 48px; height: 48px; padding: 0 6px 0 16px; border: 1px solid var(--color-border); border-radius: 9999px; background: var(--color-surface); box-shadow: var(--shadow-card); }
.search-field { min-width: 0; flex-direction: column; align-items: flex-start; justify-content: center; gap: 2px; }
.search-field-main { flex: 1; }
.search-field input { width: 100%; padding: 0; overflow: hidden; border: 0; outline: 0; background: transparent; color: var(--color-text-muted); font-size: 14px; line-height: 1.43; text-overflow: ellipsis; white-space: nowrap; }
.search-field input:focus { color: var(--color-text-primary); }
.search-field input::placeholder { color: var(--color-text-disabled); opacity: 1; }
.search-orb { display: grid; flex: 0 0 40px; width: 40px; height: 40px; padding: 0; place-items: center; border: 0; border-radius: 50%; background: var(--color-accent); color: var(--color-on-accent); cursor: pointer; }
.search-orb:hover, .search-orb:focus-visible { background: var(--color-accent-hover); }
.search-orb:active { background: var(--color-accent-hover); }
.search-orb:disabled { background: var(--color-accent-disabled); color: var(--color-on-accent-disabled); cursor: not-allowed; }
.filter-row { display: flex; align-items: flex-start; flex: 0 0 420px; gap: 24px; min-width: 0; }
.category-filter { flex: 0 0 180px; min-width: 0; }
.sort-filter { display: flex; min-width: 0; flex: 1 1 300px; flex-direction: column; align-items: flex-start; gap: 8px; }
.filter-label { color: var(--color-text-primary); font-size: 13px; font-weight: 600; }
.sort-options { display: flex; gap: 4px; padding: 4px; border-radius: 32px; background: var(--color-surface-soft); }
.sort-option { min-height: 40px; padding: 0 18px; border: 0; border-radius: 9999px; background: transparent; color: var(--color-text-muted); font-size: 14px; cursor: pointer; }
.sort-option:hover, .sort-option:focus-visible { color: var(--color-text-primary); }
.sort-option:focus-visible { outline: 2px solid var(--color-focus); outline-offset: 2px; }
.sort-option.active { background: var(--color-surface); color: var(--color-text-primary); box-shadow: var(--shadow-card); font-weight: 500; }
.sort-option:disabled { color: var(--color-text-disabled); cursor: not-allowed; opacity: .65; }
.results-heading { justify-content: space-between; margin: 64px 0 24px; }
.section-kicker { margin-bottom: 6px; color: var(--color-text-muted); font-size: 10px; letter-spacing: 1px; }
.results-heading h2 { margin: 0; color: var(--color-text-primary); font-size: 22px; font-weight: 500; letter-spacing: -.44px; line-height: 1.18; }
.result-count { margin: 20px 0 0; color: var(--color-text-muted); font-size: 14px; }
.product-grid { display: grid; grid-template-columns: repeat(4, minmax(0, 1fr)); gap: 32px 16px; }
.product-card { overflow: hidden; border-radius: 14px; background: var(--color-surface); outline: 0; cursor: pointer; }
.product-card:hover, .product-card:focus-visible { box-shadow: var(--shadow-card); }
.product-card:focus-visible { box-shadow: 0 0 0 2px var(--color-focus), var(--shadow-card); }
.card-image-wrap { position: relative; aspect-ratio: 1 / 1; overflow: hidden; border-radius: 14px; background: var(--color-surface-soft); }
.card-image-wrap img { display: block; width: 100%; height: 100%; object-fit: contain; transition: transform .25s ease; }
.product-card:hover .card-image-wrap img { transform: scale(1.03); }
.image-placeholder { display: grid; height: 100%; place-items: center; color: var(--color-text-disabled); font-size: 12px; }
.card-body { padding: 16px; }
.card-body h3 { display: -webkit-box; min-height: 40px; margin: 0 0 10px; overflow: hidden; color: var(--color-text-primary); font-size: 16px; font-weight: 600; line-height: 1.25; -webkit-line-clamp: 2; -webkit-box-orient: vertical; }
.price-row { gap: 8px; }
.price-row strong, .drawer-price-row strong { color: var(--color-accent); font-size: 20px; font-weight: 600; line-height: 1.25; }
.reference { color: var(--color-text-disabled); font-size: 12px; text-decoration: line-through; }
.price-discount { display: inline-flex; align-items: center; padding: 4px 8px; border-radius: 9999px; background: var(--color-tag-surface); color: var(--color-accent); font-size: 11px; font-weight: 600; line-height: 1.18; }
.card-meta { justify-content: space-between; min-height: 28px; margin-top: 8px; }
.tag, .tracked-tag { display: inline-flex; align-items: center; padding: 4px 8px; border-radius: 9999px; background: var(--color-tag-surface); color: var(--color-error); font-size: 11px; font-weight: 600; line-height: 1.18; }
.tracked-tag { background: var(--color-surface-soft); color: var(--color-text-muted); }
.notice { display: flex; align-items: center; justify-content: center; gap: 10px; min-height: 180px; padding: 32px 20px; border: 1px solid var(--color-border-soft); border-radius: 14px; color: var(--color-text-muted); font-size: 14px; }
.notice-icon { display: grid; width: 24px; height: 24px; place-items: center; border-radius: 50%; background: var(--color-error); color: var(--color-on-error); font-weight: 700; }
.notice button { padding: 0; border: 0; background: transparent; color: var(--color-error); font-size: 14px; text-decoration: underline; cursor: pointer; }
.empty-state { flex-direction: column; gap: 6px; }
.empty-state strong { color: var(--color-text-primary); font-size: 16px; font-weight: 600; }
.empty-icon { display: grid; width: 42px; height: 42px; margin-bottom: 6px; place-items: center; border-radius: 50%; background: var(--color-surface-strong); color: var(--color-text-muted); font-size: 22px; }
.skeleton-card { overflow: hidden; border-radius: 14px; }
.skeleton-image, .skeleton-line { background: linear-gradient(90deg, var(--color-surface-soft) 25%, var(--color-border-soft) 50%, var(--color-surface-soft) 75%); background-size: 200% 100%; animation: shimmer 1.4s infinite; }
.skeleton-image { aspect-ratio: 1 / 1; border-radius: 14px; }
.skeleton-line { height: 16px; margin: 16px 2px 0; border-radius: 8px; }
.skeleton-title { width: 76%; }
.skeleton-price { width: 38%; margin-top: 10px; }
.pagination { justify-content: center; gap: 8px; margin-top: 48px; color: var(--color-text-muted); }
.pagination button { display: grid; min-width: 40px; height: 40px; padding: 0 10px; place-items: center; border: 0; border-radius: 50%; background: transparent; color: var(--color-text-primary); font-size: 14px; cursor: pointer; }
.pagination button:hover, .pagination button:focus-visible { background: var(--color-surface-strong); }
.pagination button.active { background: var(--color-text-primary); color: var(--color-canvas); }
.pagination button:disabled { color: var(--color-text-disabled); cursor: not-allowed; opacity: .55; }
.pagination button.pagination-arrow { border: 1px solid var(--color-border); }
.page-total { margin: 0 12px; font-size: 13px; }
.external-link:hover { color: var(--color-text-primary); text-decoration: underline; }
.drawer-backdrop { position: fixed; z-index: 10; inset: 0; background: var(--color-scrim); }
.drawer { position: absolute; top: 0; right: 0; width: min(720px, 100%); height: 100%; padding: 32px 40px 48px; overflow-y: auto; background: var(--color-surface); box-shadow: var(--shadow-drawer); animation: slide-in .22s ease-out; }
.drawer-close { position: absolute; top: 20px; right: 24px; display: grid; width: 40px; height: 40px; padding: 0; place-items: center; border: 0; border-radius: 50%; background: var(--color-surface-strong); color: var(--color-text-primary); cursor: pointer; }
.drawer-close:hover, .drawer-close:focus-visible { background: var(--color-border); }
.drawer-image { aspect-ratio: 1 / .72; margin-bottom: 28px; overflow: hidden; border-radius: 14px; background: var(--color-surface-soft); }
.drawer-image img { display: block; width: 100%; height: 100%; object-fit: contain; }
.drawer-kicker { margin-bottom: 8px; font-size: 10px; }
.drawer h2 { max-width: 580px; margin: 0 48px 16px 0; color: var(--color-text-primary); font-size: 22px; font-weight: 500; letter-spacing: -.44px; line-height: 1.18; }
.drawer-price-row { gap: 10px; }
.drawer-price-row strong { font-size: 22px; }
.tag-row { display: flex; gap: 8px; min-height: 28px; margin-top: 14px; }
.drawer-error { margin: 24px 0 0; padding: 12px 14px; border-radius: 8px; background: var(--color-error-surface); color: var(--color-error); font-size: 13px; }
.detail-section { margin-top: 32px; padding-top: 24px; border-top: 1px solid var(--color-border-soft); }
.section-title { justify-content: space-between; gap: 16px; margin-bottom: 16px; }
.section-title h3 { margin: 0; color: var(--color-text-primary); font-size: 20px; font-weight: 600; line-height: 1.2; }
.section-title span { color: var(--color-text-disabled); font-size: 12px; }
.detail-facts { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 12px 24px; }
.detail-facts p { display: flex; align-items: baseline; justify-content: space-between; gap: 12px; margin: 0; padding: 12px 0; border-bottom: 1px solid var(--color-surface-strong); color: var(--color-text-muted); font-size: 14px; }
.detail-facts strong { color: var(--color-text-primary); font-weight: 500; text-align: right; }
.detail-section p.muted { margin: 0; color: var(--color-text-disabled); font-size: 14px; }
.muted { color: var(--color-text-disabled) !important; }
.attribute-list { display: grid; gap: 8px; margin-top: 16px; }
.attribute-list div { display: flex; align-items: center; justify-content: space-between; gap: 12px; padding: 11px 12px; border-radius: 8px; background: var(--color-surface-soft); font-size: 13px; }
.attribute-list span { color: var(--color-text-muted); }
.attribute-list strong { color: var(--color-text-primary); font-weight: 500; }
.trend-chart { width: 100%; height: 260px; }
.external-link { display: inline-flex; align-items: center; gap: 6px; margin-top: 32px; color: var(--color-text-primary); font-size: 14px; text-underline-offset: 4px; }
.drawer-state { display: flex; min-height: 360px; align-items: center; justify-content: center; gap: 12px; color: var(--color-text-muted); font-size: 14px; }
.loader { width: 18px; height: 18px; border: 2px solid var(--color-accent-disabled); border-top-color: var(--color-accent); border-radius: 50%; animation: spin .8s linear infinite; }
@keyframes slide-in { from { transform: translateX(100%); } to { transform: translateX(0); } }
@keyframes spin { to { transform: rotate(360deg); } }
@keyframes shimmer { to { background-position: -200% 0; } }
@media (max-width: 1128px) {
  .page-shell { width: min(100% - 48px, 960px); }
  .product-grid { grid-template-columns: repeat(3, minmax(0, 1fr)); }
}
@media (max-width: 744px) {
  .page-shell { width: min(100% - 32px, 560px); }
  .top-nav { height: 64px; }
  .brand-name, .product-nav { display: none; }
  .hero { padding: 48px 0 32px; }
  .search-filter-row { display: block; }
  .search-bar { height: 48px; padding-left: 18px; }
  .search-orb { flex-basis: 40px; width: 40px; height: 40px; font-size: 24px; }
  .filter-row { align-items: stretch; flex-direction: column; gap: 16px; margin-top: 16px; }
  .category-filter { width: 100%; flex-basis: auto; }
  .sort-filter { flex: none; }
  .sort-options { width: 100%; }
  .sort-option { flex: 1; padding: 0 12px; }
  .results-heading { margin-top: 48px; }
  .product-grid { grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 28px 12px; }
  .card-body { padding: 16px; }
  .card-body h3 { font-size: 14px; }
  .price-row strong { font-size: 16px; }
  .drawer { padding: 24px 20px 40px; }
  .drawer-image { margin-top: 36px; }
  .detail-facts { gap: 0 16px; }
}
@media (max-width: 420px) {
  .page-shell { width: calc(100% - 24px); }
  .search-label { font-size: 11px; }
  .search-field input { font-size: 13px; }
  .detail-facts { display: block; }
  .drawer h2 { font-size: 20px; }
}
@media (prefers-reduced-motion: reduce) {
  :global(html) { scroll-behavior: auto; }
  *, *::before, *::after { animation-duration: .01ms !important; transition-duration: .01ms !important; }
}
</style>
