<script setup>
import { computed, onMounted, ref, watch } from 'vue'
import { fetchProductDeals, fetchProductDetails, fetchProductHistory, fetchProductPricePoints, fetchProducts } from '../api/products'

const products = ref([])
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
  selectedProduct.value = product
  drawerData.value = null
  drawerError.value = ''
  drawerLoading.value = true
  document.body.style.overflow = 'hidden'
  Promise.allSettled([
    fetchProductDetails(product.cluster_id),
    fetchProductHistory(product.cluster_id),
    fetchProductDeals(product.cluster_id),
    fetchProductPricePoints(product.cluster_id),
  ]).then(([details, history, deals, points]) => {
    drawerData.value = {
      basic: product,
      details: details.status === 'fulfilled' ? (details.value.detail || details.value) : null,
      history: history.status === 'fulfilled' ? history.value.items || [] : [],
      deals: deals.status === 'fulfilled' ? deals.value.items || [] : [],
      points: points.status === 'fulfilled' ? points.value.items || [] : [],
    }
    if ([details, history, deals, points].every((result) => result.status === 'rejected')) drawerError.value = '详情暂时无法加载，请稍后重试'
  }).finally(() => {
    drawerLoading.value = false
  })
}

function closeProduct() {
  selectedProduct.value = null
  document.body.style.overflow = ''
}

function formatPrice(value) {
  return value === null || value === undefined ? '暂无价格' : `¥${Number(value).toFixed(2)}`
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

onMounted(loadProducts)
watch(category, resetAndLoad)
</script>

<template>
  <main class="page-shell">
    <header class="hero">
      <div>
        <p class="eyebrow">PRODUCT TRACKER</p>
        <h1>发现值得关注的商品</h1>
        <p class="subtitle">追踪价格变化，掌握每一次上新与机会。</p>
      </div>
      <div class="status-pill"><span class="status-dot" /> 数据中心</div>
    </header>

    <section class="toolbar" aria-label="商品筛选">
      <form class="search-box" @submit.prevent="submitSearch"><span>⌕</span><input v-model="search" placeholder="搜索商品名称" /></form>
      <select v-model="category" aria-label="商品分类">
        <option value="">全部分类</option>
        <option value="898">3C 数码</option>
        <option value="142">手办</option>
      </select>
      <button class="refresh-button" :disabled="loading" @click="loadProducts">{{ loading ? '加载中…' : '刷新' }}</button>
    </section>

    <p v-if="error" class="notice error">{{ error }} <button @click="loadProducts">重试</button></p>
    <div v-else-if="loading" class="notice">正在加载商品…</div>
    <div v-else-if="products.length === 0" class="notice">没有找到匹配的商品</div>

    <section v-else class="product-grid">
      <article v-for="product in products" :key="product.cluster_id" class="product-card" @click="openProduct(product)">
        <div class="card-image-wrap">
          <img v-if="product.img && !imageErrors.has(product.cluster_id)" :src="normalizeImageUrl(product.img)" :alt="product.title" loading="lazy" referrerpolicy="no-referrer" @error="imageFailed(product.cluster_id)" />
          <div v-else class="image-placeholder">NO IMAGE</div>
        </div>
        <div class="card-body">
          <p class="card-category">{{ product.category || '未分类' }}</p>
          <h2>{{ product.title }}</h2>
          <div class="price-row"><strong>{{ formatPrice(product.price) }}</strong><span v-if="product.reference_price" class="reference">¥{{ Number(product.reference_price).toFixed(2) }}</span></div>
          <div class="tag-row"><span v-if="product.discount" class="tag">{{ product.discount }}</span><span v-if="product.popularity" class="popularity">{{ product.popularity }}</span></div>
        </div>
      </article>
    </section>

    <nav v-if="total > 0" class="pagination" aria-label="分页">
      <button :disabled="page === 1 || loading" @click="page--; loadProducts()">上一页</button>
      <button v-for="number in pageNumbers" :key="number" :class="{ active: number === page }" :disabled="loading" @click="page = number; loadProducts()">{{ number }}</button>
      <span class="page-total">共 {{ totalPages }} 页 · {{ total }} 件</span>
      <button :disabled="page === totalPages || loading" @click="page++; loadProducts()">下一页</button>
    </nav>

    <div v-if="selectedProduct" class="drawer-backdrop" @click="closeProduct">
      <aside class="drawer" @click.stop>
        <button class="drawer-close" aria-label="关闭详情" @click="closeProduct">×</button>
        <div v-if="drawerLoading" class="drawer-state">正在加载商品详情…</div>
        <template v-else>
          <div class="drawer-image"><img v-if="selectedProduct.img" :src="normalizeImageUrl(selectedProduct.img)" :alt="selectedProduct.title" referrerpolicy="no-referrer" /></div>
          <p class="card-category">{{ selectedProduct.category || '未分类' }}</p>
          <h2>{{ selectedProduct.title }}</h2>
          <div class="price-row"><strong>{{ formatPrice((drawerData?.basic || selectedProduct).price) }}</strong><span v-if="(drawerData?.basic || selectedProduct).reference_price" class="reference">¥{{ Number((drawerData?.basic || selectedProduct).reference_price).toFixed(2) }}</span></div>
          <div class="tag-row"><span v-if="selectedProduct.discount" class="tag">{{ selectedProduct.discount }}</span><span v-if="selectedProduct.popularity" class="popularity">{{ selectedProduct.popularity }}</span></div>
          <p v-if="drawerError" class="drawer-error">{{ drawerError }}</p>
          <section v-if="drawerData?.details" class="detail-section"><h3>详情信息</h3><p>当前价：{{ drawerData.details.price_tag?.firstPrice ? `${drawerData.details.price_tag.firstPriceSymbol || '¥'}${drawerData.details.price_tag.firstPrice}` : '暂无' }}</p><p>参考价：{{ drawerData.details.price_tag?.price ? `${drawerData.details.price_tag.priceSymbol || '¥'}${drawerData.details.price_tag.price}` : '暂无' }}</p><p>最低价：{{ drawerData.details.lowest_price || '暂无' }}</p><p>最近成交价：{{ drawerData.details.latest_deal_price || '暂无' }}</p><div v-if="drawerData.details.attributes?.length" class="attribute-list"><div v-for="item in drawerData.details.attributes" :key="item.name"><span>{{ item.name }}</span><strong>{{ item.value }}</strong></div></div></section>
          <section class="detail-section"><h3>价格历史</h3><div v-if="drawerData?.history?.length" class="history-list"><div v-for="item in drawerData.history" :key="item.captured_at"><strong>{{ formatPrice(item.price) }}</strong><span>{{ item.captured_at }}</span></div></div><p v-else class="muted">暂无价格历史</p></section>
          <section class="detail-section"><h3>价格走势 <small>{{ drawerData?.points?.length || 0 }}</small></h3><div v-if="drawerData?.points?.length" class="history-list"><div v-for="item in drawerData.points.slice(0, 20)" :key="`${item.date_label}-${item.avg_price}`"><strong>{{ item.avg_price || '暂无' }}</strong><span>{{ item.date_label }} · {{ item.volume || 0 }} 笔</span></div></div><p v-else class="muted">暂无走势数据</p></section>
          <section class="detail-section"><h3>成交记录 <small>{{ drawerData?.deals?.length || 0 }}</small></h3><div v-if="drawerData?.deals?.length" class="deal-list"><div v-for="(item, index) in drawerData.deals.slice(0, 20)" :key="index"><span class="deal-user">{{ item.user_name || '匿名用户' }}</span><strong>{{ item.deal_price || '暂无' }}</strong><small>{{ item.deal_time || '' }}</small></div></div><p v-else class="muted">暂无成交记录</p></section>
          <a v-if="selectedProduct.url" class="external-link" :href="selectedProduct.url" target="_blank" rel="noopener">查看商品页面 ↗</a>
        </template>
      </aside>
    </div>
  </main>
</template>

<style scoped>
:global(*) { box-sizing: border-box; }
:global(body) { margin: 0; background: #f5f7fb; color: #172033; font-family: Inter, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif; }
.page-shell { width: min(1240px, calc(100% - 40px)); margin: 0 auto; padding: 52px 0 72px; }
.hero { display: flex; align-items: flex-end; justify-content: space-between; margin-bottom: 34px; }
.eyebrow { margin: 0 0 12px; color: #64748b; font-size: 11px; font-weight: 700; letter-spacing: .2em; }
h1 { margin: 0; font-size: clamp(30px, 4vw, 48px); letter-spacing: -.04em; }
.subtitle { margin: 14px 0 0; color: #718096; font-size: 15px; }
.status-pill { padding: 9px 14px; border: 1px solid #e5eaf2; border-radius: 999px; background: #fff; color: #64748b; font-size: 13px; }
.status-dot { display: inline-block; width: 7px; height: 7px; margin-right: 7px; border-radius: 50%; background: #39b87f; }
.toolbar { display: flex; gap: 12px; margin-bottom: 28px; }
.search-box { display: flex; align-items: center; flex: 1; gap: 8px; padding: 0 15px; border: 1px solid #e4e9f1; border-radius: 12px; background: #fff; color: #94a3b8; }
input, select, button { font: inherit; }
input { width: 100%; padding: 13px 0; border: 0; outline: 0; color: #172033; background: transparent; }
select, button { padding: 0 16px; border: 1px solid #e4e9f1; border-radius: 12px; background: #fff; color: #334155; cursor: pointer; }
select { min-width: 130px; }
button { min-height: 44px; } button:disabled { cursor: not-allowed; opacity: .5; }
.refresh-button { background: #172033; color: #fff; border-color: #172033; }
.product-grid { display: grid; grid-template-columns: repeat(4, minmax(0, 1fr)); gap: 18px; }
.product-card { overflow: hidden; border: 1px solid #e9edf4; border-radius: 16px; background: #fff; box-shadow: 0 8px 28px rgba(34, 48, 74, .05); transition: transform .2s, box-shadow .2s; }
.product-card:hover { transform: translateY(-3px); box-shadow: 0 14px 34px rgba(34, 48, 74, .11); }
.card-image-wrap { display: block; aspect-ratio: 1.2; background: #f1f4f8; } .card-image-wrap img { width: 100%; height: 100%; object-fit: cover; }
.image-placeholder { display: grid; height: 100%; place-items: center; color: #a0aec0; font-size: 12px; letter-spacing: .12em; }
.card-body { padding: 16px; } .card-category { margin: 0 0 8px; color: #8a96a8; font-size: 12px; }
h2 { display: -webkit-box; min-height: 44px; margin: 0 0 14px; overflow: hidden; font-size: 15px; line-height: 1.5; -webkit-line-clamp: 2; -webkit-box-orient: vertical; }
.price-row { display: flex; align-items: baseline; gap: 8px; } .price-row strong { color: #dc4d5d; font-size: 20px; } .reference { color: #a0aec0; font-size: 12px; text-decoration: line-through; }
.tag-row { display: flex; gap: 6px; min-height: 24px; margin-top: 12px; } .tag, .popularity { padding: 4px 7px; border-radius: 5px; font-size: 11px; } .tag { background: #fff0f1; color: #d45763; } .popularity { background: #f0f5ff; color: #6580ba; }
.notice { padding: 54px 20px; text-align: center; color: #718096; } .error { color: #c2414c; } .notice button { min-height: 34px; margin-left: 8px; padding: 0 10px; }
.pagination { display: flex; align-items: center; justify-content: center; gap: 8px; margin-top: 34px; color: #64748b; font-size: 13px; flex-wrap: wrap; } .pagination button { min-width: 42px; } .pagination button.active { background: #172033; color: #fff; border-color: #172033; } .page-total { margin: 0 8px; }
.drawer-backdrop { position: fixed; z-index: 10; inset: 0; background: rgba(15, 23, 42, .32); } .drawer { position: absolute; top: 0; right: 0; width: min(440px, 100%); height: 100%; padding: 32px; overflow-y: auto; background: #fff; box-shadow: -12px 0 32px rgba(15, 23, 42, .12); animation: slide-in .22s ease-out; } .drawer-close { position: absolute; top: 18px; right: 18px; min-height: 36px; padding: 0 12px; border: 0; background: transparent; font-size: 28px; } .drawer-image { aspect-ratio: 1.1; margin-bottom: 24px; overflow: hidden; border-radius: 14px; background: #f1f4f8; } .drawer-image img { width: 100%; height: 100%; object-fit: cover; } .external-link { display: inline-block; margin-top: 28px; color: #536da4; text-decoration: none; } @keyframes slide-in { from { transform: translateX(100%); } to { transform: translateX(0); } }
.drawer-state { padding: 100px 0; text-align: center; color: #718096; }.drawer-error { padding: 10px 12px; border-radius: 8px; background: #fff4f4; color: #c2414c; font-size: 13px; }.detail-section { margin-top: 26px; padding-top: 20px; border-top: 1px solid #edf0f5; }.detail-section h3 { margin: 0 0 12px; font-size: 14px; }.detail-section h3 small { color: #94a3b8; font-size: 12px; font-weight: 400; }.detail-section p { margin: 7px 0; color: #64748b; font-size: 13px; }.muted { color: #a0aec0 !important; }.history-list { display: grid; gap: 8px; }.history-list div { display: flex; align-items: center; justify-content: space-between; padding: 10px 12px; border-radius: 8px; background: #f7f9fc; }.history-list strong { color: #d84e5d; font-size: 14px; }.history-list span { color: #94a3b8; font-size: 11px; }
.attribute-list, .deal-list { display: grid; gap: 7px; }.attribute-list div, .deal-list div { display: flex; align-items: center; gap: 10px; padding: 9px 11px; border-radius: 8px; background: #f7f9fc; font-size: 12px; }.attribute-list span { color: #94a3b8; min-width: 48px; }.attribute-list strong { color: #475569; font-weight: 500; }.deal-list div { justify-content: space-between; }.deal-user { overflow: hidden; color: #64748b; text-overflow: ellipsis; white-space: nowrap; }.deal-list strong { color: #d84e5d; }.deal-list small { color: #94a3b8; }
@media (max-width: 900px) { .product-grid { grid-template-columns: repeat(3, minmax(0, 1fr)); } }
@media (max-width: 640px) { .page-shell { width: min(100% - 24px, 520px); padding-top: 30px; } .hero { align-items: flex-start; flex-direction: column; gap: 18px; } .toolbar { flex-wrap: wrap; } .search-box { flex-basis: 100%; } .product-grid { grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 12px; } .card-body { padding: 12px; } }
</style>
