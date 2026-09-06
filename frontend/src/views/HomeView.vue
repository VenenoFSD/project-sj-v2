<script setup>
import { computed, nextTick, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { LineChart } from 'echarts/charts'
import { GridComponent, TooltipComponent } from 'echarts/components'
import * as echarts from 'echarts/core'
import { CanvasRenderer } from 'echarts/renderers'
import { ArrowRight, ArrowUpRight, ChevronLeft, ChevronRight, Heart, House, RefreshCw, Search, Sparkles, X } from 'lucide-vue-next'
import { fetchCatalog } from '../api/catalog'
import { fetchProductDeals, fetchProductDetails, fetchProductHistory, fetchProducts } from '../api/products'

echarts.use([LineChart, GridComponent, TooltipComponent, CanvasRenderer])

const products = ref([])
const categories = ref([])
const category = ref('')
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
let priceChart
let dealChart

const totalPages = computed(() => Math.max(1, Math.ceil(total.value / pageSize)))
const pageNumbers = computed(() => {
  const start = Math.max(1, Math.min(page.value - 2, totalPages.value - 4))
  return Array.from({ length: Math.min(5, totalPages.value) }, (_, index) => start + index)
})

async function loadProducts() {
  loading.value = true
  error.value = ''
  try {
    const data = await fetchProducts({ category: category.value, search: submittedSearch.value, limit: pageSize, offset: (page.value - 1) * pageSize })
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

function parseTrendValue(value) {
  if (value === null || value === undefined) return null
  const match = String(value).replace(/,/g, '').match(/-?\d+(?:\.\d+)?/)
  return match ? Number(match[0]) : null
}

function getTrendData(items, valueKey, labelKey) {
  return items
    .map((item) => ({ value: parseTrendValue(item[valueKey]), label: item[labelKey] || '' }))
    .filter((item) => Number.isFinite(item.value))
    .reverse()
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

function renderTrendChart(element, data, color, seriesName) {
  if (!element || !data.length) return null
  const chart = echarts.getInstanceByDom(element) || echarts.init(element)
  chart.setOption({
    animationDuration: 350,
    grid: { top: 18, right: 18, bottom: 34, left: 46 },
    tooltip: {
      trigger: 'axis',
      confine: true,
      formatter: (params) => {
        const point = params[0]
        return `${formatTrendTime(point.axisValue)}<br/>${point.marker}${point.seriesName}：¥${Number(point.value).toFixed(2)}`
      },
    },
    xAxis: {
      type: 'category',
      boundaryGap: false,
      data: data.map((item) => item.label),
      axisLabel: { color: '#94a3b8', hideOverlap: true, formatter: formatTrendLabel },
      axisLine: { lineStyle: { color: '#e9edf4' } },
      axisTick: { show: false },
    },
    yAxis: {
      type: 'value',
      scale: true,
      axisLabel: { color: '#94a3b8', formatter: (value) => `¥${Number(value).toFixed(0)}` },
      axisLine: { show: false },
      axisTick: { show: false },
      splitLine: { lineStyle: { color: '#edf0f5' } },
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
      itemStyle: { color, borderColor: '#fff', borderWidth: 2 },
      areaStyle: { color, opacity: 0.12 },
      emphasis: { focus: 'series' },
    }],
  })
  return chart
}

const priceTrendData = computed(() => getTrendData(drawerData.value?.history || [], 'price', 'captured_at'))
const dealTrendData = computed(() => getTrendData(drawerData.value?.deals || [], 'deal_price', 'deal_time'))

function renderCharts() {
  nextTick(() => {
    disposeCharts()
    priceChart = renderTrendChart(priceChartElement.value, priceTrendData.value, '#dc4d5d', '挂牌价')
    dealChart = renderTrendChart(dealChartElement.value, dealTrendData.value, '#536da4', '成交价')
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
  loadProducts()
  loadCategories()
  window.addEventListener('resize', resizeCharts)
})
onBeforeUnmount(() => {
  window.removeEventListener('resize', resizeCharts)
  disposeCharts()
  document.body.style.overflow = ''
})
watch(category, resetAndLoad)
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
    </header>

    <section class="hero" aria-labelledby="page-title">
      <h1 id="page-title">发现值得关注的商品</h1>
    </section>

    <section id="products" class="search-section" aria-label="商品筛选">
      <form class="search-bar" @submit.prevent="submitSearch">
        <div class="search-field search-field-main">
          <span class="search-label">搜索商品</span>
          <input v-model="search" aria-label="搜索商品名称" placeholder="输入商品名称" />
        </div>
        <button class="search-orb" type="submit" aria-label="搜索" :disabled="loading"><Search :size="20" :stroke-width="2.2" aria-hidden="true" /></button>
      </form>
      <button class="refresh-button" type="button" :disabled="loading" @click="loadProducts">
        <RefreshCw :size="18" :stroke-width="2" :class="{ spinning: loading }" aria-hidden="true" />
        <span>{{ loading ? '加载中' : '刷新商品' }}</span>
      </button>
    </section>

    <div v-if="categories.length" class="category-strip" aria-label="分类快捷筛选">
      <button class="category-tab" :class="{ active: category === '' }" type="button" @click="category = ''">全部</button>
      <button v-for="item in categories" :key="item.item_id" class="category-tab" :class="{ active: category === item.item_id }" type="button" @click="category = item.item_id">{{ item.name || item.item_id }}</button>
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
          <span class="card-arrow" aria-hidden="true"><ArrowUpRight :size="17" :stroke-width="1.8" /></span>
        </div>
        <div class="card-body">
          <h3>{{ product.title }}</h3>
          <div class="price-row"><strong>{{ formatPrice(product.price) }}</strong><span v-if="product.reference_price" class="reference">¥{{ Number(product.reference_price).toFixed(2) }}</span></div>
          <div class="card-meta"><span v-if="product.discount" class="tag">{{ product.discount }}</span><span class="detail-link">查看详情 <ArrowRight :size="15" :stroke-width="1.8" aria-hidden="true" /></span></div>
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
          <div class="drawer-price-row"><strong>{{ formatPrice((drawerData?.basic || selectedProduct).price) }}</strong><span v-if="(drawerData?.basic || selectedProduct).reference_price" class="reference">¥{{ Number((drawerData?.basic || selectedProduct).reference_price).toFixed(2) }}</span></div>
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
:global(body) { margin: 0; background: #fff; color: #222; font-family: "Airbnb Cereal VF", Circular, Inter, -apple-system, system-ui, Roboto, "Helvetica Neue", sans-serif; }
:global(button), :global(input), :global(select) { font: inherit; }
:global(button), :global(a) { -webkit-tap-highlight-color: transparent; }
.page-shell { width: min(1280px, calc(100% - 64px)); margin: 0 auto; padding-bottom: 64px; }
.top-nav { display: flex; align-items: center; justify-content: space-between; height: 80px; border-bottom: 1px solid #ebebeb; }
.brand, .product-tab, .search-bar, .search-field, .category-strip, .results-heading, .price-row, .card-meta, .pagination, .section-title, .drawer-price-row { display: flex; align-items: center; }
.top-nav { position: relative; justify-content: center; }
.brand { position: absolute; left: 0; gap: 9px; color: #222; font-size: 16px; font-weight: 600; text-decoration: none; }
.brand-mark { display: grid; width: 32px; height: 32px; place-items: center; border-radius: 50%; background: #ff385c; color: #fff; font-size: 18px; font-weight: 700; }
.brand-name { letter-spacing: -.2px; }
.product-nav { display: flex; align-self: stretch; gap: 34px; }
.product-tab { position: relative; gap: 7px; color: #6a6a6a; font-size: 14px; font-weight: 500; text-decoration: none; }
.product-tab:hover, .product-tab:focus-visible { color: #222; }
.product-tab.active { color: #222; font-weight: 600; }
.product-tab.active::after { position: absolute; right: 0; bottom: 0; left: 0; height: 2px; background: #222; content: ""; }
.product-icon { display: grid; width: 24px; height: 24px; place-items: center; }
.new-tag { position: absolute; top: 16px; right: -23px; padding: 2px 6px; border-radius: 9999px; background: #f2f2f2; color: #222; font-size: 8px; font-weight: 700; letter-spacing: .32px; line-height: 1.25; }
.hero { padding: 64px 0 40px; text-align: center; }
.section-kicker, .drawer-kicker { margin: 0 0 12px; color: #ff385c; font-size: 11px; font-weight: 700; letter-spacing: 1.2px; line-height: 1.3; }
.hero h1 { margin: 0; color: #222; font-size: clamp(24px, 3vw, 28px); font-weight: 700; letter-spacing: 0; line-height: 1.43; }
.search-section { display: flex; align-items: center; gap: 12px; max-width: 850px; margin: 0 auto; }
.search-bar { flex: 1; height: 64px; padding: 8px 8px 8px 24px; border: 1px solid #ddd; border-radius: 9999px; background: #fff; box-shadow: rgba(0, 0, 0, .02) 0 0 0 1px, rgba(0, 0, 0, .04) 0 2px 6px, rgba(0, 0, 0, .1) 0 4px 8px; }
.search-field { min-width: 0; flex-direction: column; align-items: flex-start; justify-content: center; gap: 2px; }
.search-field-main { flex: 1; }
.search-label { color: #222; font-size: 12px; font-weight: 600; line-height: 1.33; }
.search-field input { width: 100%; padding: 0; overflow: hidden; border: 0; outline: 0; background: transparent; color: #6a6a6a; font-size: 14px; line-height: 1.43; text-overflow: ellipsis; white-space: nowrap; }
.search-field input:focus { color: #222; }
.search-field input::placeholder { color: #929292; opacity: 1; }
.search-orb { display: grid; flex: 0 0 48px; width: 48px; height: 48px; padding: 0; place-items: center; border: 0; border-radius: 50%; background: #ff385c; color: #fff; cursor: pointer; }
.search-orb:hover, .search-orb:focus-visible, .refresh-button:hover, .refresh-button:focus-visible { background: #e00b41; }
.search-orb:active, .refresh-button:active { background: #e00b41; }
.search-orb:disabled { background: #ffd1da; cursor: not-allowed; }
.refresh-button { display: inline-flex; align-items: center; justify-content: center; gap: 8px; height: 48px; padding: 0 18px; border: 0; border-radius: 8px; background: #ff385c; color: #fff; font-size: 14px; font-weight: 500; cursor: pointer; white-space: nowrap; }
.refresh-button:disabled { background: #ffd1da; cursor: not-allowed; }
.spinning { animation: spin .8s linear infinite; }
.category-strip { justify-content: center; gap: 4px; margin: 32px auto 0; padding: 4px; overflow-x: auto; border-radius: 32px; background: #f7f7f7; scrollbar-width: none; }
.category-strip::-webkit-scrollbar { display: none; }
.category-tab { flex: 0 0 auto; min-height: 40px; padding: 0 18px; border: 0; border-radius: 9999px; background: transparent; color: #6a6a6a; font-size: 14px; cursor: pointer; }
.category-tab:hover, .category-tab:focus-visible { color: #222; }
.category-tab.active { background: #fff; color: #222; box-shadow: rgba(0, 0, 0, .02) 0 0 0 1px, rgba(0, 0, 0, .04) 0 2px 6px, rgba(0, 0, 0, .1) 0 4px 8px; font-weight: 500; }
.results-heading { justify-content: space-between; margin: 64px 0 24px; }
.section-kicker { margin-bottom: 6px; color: #6a6a6a; font-size: 10px; letter-spacing: 1px; }
.results-heading h2 { margin: 0; color: #222; font-size: 22px; font-weight: 500; letter-spacing: -.44px; line-height: 1.18; }
.result-count { margin: 20px 0 0; color: #6a6a6a; font-size: 14px; }
.product-grid { display: grid; grid-template-columns: repeat(4, minmax(0, 1fr)); gap: 32px 16px; }
.product-card { overflow: hidden; border-radius: 14px; background: #fff; outline: 0; cursor: pointer; }
.product-card:hover, .product-card:focus-visible { box-shadow: rgba(0, 0, 0, .02) 0 0 0 1px, rgba(0, 0, 0, .04) 0 2px 6px, rgba(0, 0, 0, .1) 0 4px 8px; }
.product-card:focus-visible { box-shadow: 0 0 0 2px #222, rgba(0, 0, 0, .1) 0 4px 8px; }
.card-image-wrap { position: relative; aspect-ratio: 1 / 1; overflow: hidden; border-radius: 14px; background: #f7f7f7; }
.card-image-wrap img { display: block; width: 100%; height: 100%; object-fit: contain; transition: transform .25s ease; }
.product-card:hover .card-image-wrap img { transform: scale(1.03); }
.image-placeholder { display: grid; height: 100%; place-items: center; color: #929292; font-size: 12px; }
.card-arrow { position: absolute; right: 12px; bottom: 12px; display: grid; width: 32px; height: 32px; place-items: center; border-radius: 50%; background: #f2f2f2; color: #222; font-size: 17px; opacity: 0; transition: opacity .2s ease; }
.product-card:hover .card-arrow, .product-card:focus-visible .card-arrow { opacity: 1; }
.card-body { padding: 16px; }
.card-body h3 { display: -webkit-box; min-height: 40px; margin: 0 0 10px; overflow: hidden; color: #222; font-size: 16px; font-weight: 600; line-height: 1.25; -webkit-line-clamp: 2; -webkit-box-orient: vertical; }
.price-row { gap: 8px; }
.price-row strong, .drawer-price-row strong { color: #ff385c; font-size: 20px; font-weight: 600; line-height: 1.25; }
.reference { color: #929292; font-size: 12px; text-decoration: line-through; }
.card-meta { justify-content: space-between; min-height: 28px; margin-top: 8px; }
.tag, .tracked-tag { display: inline-flex; align-items: center; padding: 4px 8px; border-radius: 9999px; background: #fff0f2; color: #c13515; font-size: 11px; font-weight: 600; line-height: 1.18; }
.tracked-tag { background: #f7f7f7; color: #6a6a6a; }
.detail-link { display: inline-flex; align-items: center; gap: 4px; color: #6a6a6a; font-size: 13px; opacity: 0; transition: opacity .2s ease; }
.product-card:hover .detail-link, .product-card:focus-visible .detail-link { opacity: 1; }
.notice { display: flex; align-items: center; justify-content: center; gap: 10px; min-height: 180px; padding: 32px 20px; border: 1px solid #ebebeb; border-radius: 14px; color: #6a6a6a; font-size: 14px; }
.notice-icon { display: grid; width: 24px; height: 24px; place-items: center; border-radius: 50%; background: #c13515; color: #fff; font-weight: 700; }
.notice button { padding: 0; border: 0; background: transparent; color: #c13515; font-size: 14px; text-decoration: underline; cursor: pointer; }
.empty-state { flex-direction: column; gap: 6px; }
.empty-state strong { color: #222; font-size: 16px; font-weight: 600; }
.empty-icon { display: grid; width: 42px; height: 42px; margin-bottom: 6px; place-items: center; border-radius: 50%; background: #f2f2f2; color: #6a6a6a; font-size: 22px; }
.skeleton-card { overflow: hidden; border-radius: 14px; }
.skeleton-image, .skeleton-line { background: linear-gradient(90deg, #f7f7f7 25%, #ebebeb 50%, #f7f7f7 75%); background-size: 200% 100%; animation: shimmer 1.4s infinite; }
.skeleton-image { aspect-ratio: 1 / 1; border-radius: 14px; }
.skeleton-line { height: 16px; margin: 16px 2px 0; border-radius: 8px; }
.skeleton-title { width: 76%; }
.skeleton-price { width: 38%; margin-top: 10px; }
.pagination { justify-content: center; gap: 8px; margin-top: 48px; color: #6a6a6a; }
.pagination button { display: grid; min-width: 40px; height: 40px; padding: 0 10px; place-items: center; border: 0; border-radius: 50%; background: transparent; color: #222; font-size: 14px; cursor: pointer; }
.pagination button:hover, .pagination button:focus-visible { background: #f2f2f2; }
.pagination button.active { background: #222; color: #fff; }
.pagination button:disabled { color: #929292; cursor: not-allowed; opacity: .55; }
.pagination button.pagination-arrow { border: 1px solid #ddd; }
.page-total { margin: 0 12px; font-size: 13px; }
.external-link:hover { color: #222; text-decoration: underline; }
.drawer-backdrop { position: fixed; z-index: 10; inset: 0; background: rgba(0, 0, 0, .5); }
.drawer { position: absolute; top: 0; right: 0; width: min(720px, 100%); height: 100%; padding: 32px 40px 48px; overflow-y: auto; background: #fff; box-shadow: -8px 0 20px rgba(0, 0, 0, .08); animation: slide-in .22s ease-out; }
.drawer-close { position: absolute; top: 20px; right: 24px; display: grid; width: 40px; height: 40px; padding: 0; place-items: center; border: 0; border-radius: 50%; background: #f2f2f2; color: #222; font-size: 26px; line-height: 1; cursor: pointer; }
.drawer-close:hover, .drawer-close:focus-visible { background: #ddd; }
.drawer-image { aspect-ratio: 1 / .72; margin-bottom: 28px; overflow: hidden; border-radius: 14px; background: #f7f7f7; }
.drawer-image img { display: block; width: 100%; height: 100%; object-fit: contain; }
.drawer-kicker { margin-bottom: 8px; font-size: 10px; }
.drawer h2 { max-width: 580px; margin: 0 48px 16px 0; color: #222; font-size: 22px; font-weight: 500; letter-spacing: -.44px; line-height: 1.18; }
.drawer-price-row { gap: 10px; }
.drawer-price-row strong { font-size: 22px; }
.tag-row { display: flex; gap: 8px; min-height: 28px; margin-top: 14px; }
.drawer-error { margin: 24px 0 0; padding: 12px 14px; border-radius: 8px; background: #fff4f2; color: #c13515; font-size: 13px; }
.detail-section { margin-top: 32px; padding-top: 24px; border-top: 1px solid #ebebeb; }
.section-title { justify-content: space-between; gap: 16px; margin-bottom: 16px; }
.section-title h3 { margin: 0; color: #222; font-size: 20px; font-weight: 600; line-height: 1.2; }
.section-title span { color: #929292; font-size: 12px; }
.detail-facts { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 12px 24px; }
.detail-facts p { display: flex; align-items: baseline; justify-content: space-between; gap: 12px; margin: 0; padding: 12px 0; border-bottom: 1px solid #f2f2f2; color: #6a6a6a; font-size: 14px; }
.detail-facts strong { color: #222; font-weight: 500; text-align: right; }
.detail-section p.muted { margin: 0; color: #929292; font-size: 14px; }
.muted { color: #929292 !important; }
.attribute-list { display: grid; gap: 8px; margin-top: 16px; }
.attribute-list div { display: flex; align-items: center; justify-content: space-between; gap: 12px; padding: 11px 12px; border-radius: 8px; background: #f7f7f7; font-size: 13px; }
.attribute-list span { color: #6a6a6a; }
.attribute-list strong { color: #222; font-weight: 500; }
.trend-chart { width: 100%; height: 260px; }
.external-link { display: inline-flex; align-items: center; gap: 6px; margin-top: 32px; color: #222; font-size: 14px; text-underline-offset: 4px; }
.drawer-state { display: flex; min-height: 360px; align-items: center; justify-content: center; gap: 12px; color: #6a6a6a; font-size: 14px; }
.loader { width: 18px; height: 18px; border: 2px solid #ffd1da; border-top-color: #ff385c; border-radius: 50%; animation: spin .8s linear infinite; }
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
  .search-section { display: block; }
  .search-bar { height: 56px; padding-left: 18px; }
  .search-orb { flex-basis: 40px; width: 40px; height: 40px; font-size: 24px; }
  .refresh-button { width: 100%; margin-top: 12px; }
  .category-strip { justify-content: flex-start; margin-top: 24px; }
  .results-heading { margin-top: 48px; }
  .product-grid { grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 28px 12px; }
  .card-body { padding: 16px; }
  .card-body h3 { font-size: 14px; }
  .price-row strong { font-size: 16px; }
  .detail-link { display: none; }
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
