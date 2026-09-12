<script setup>
import { computed, onMounted, ref, watch } from 'vue'
import { ChevronLeft, ChevronRight, Search } from 'lucide-vue-next'
import { fetchCatalog } from '../api/catalog'
import { fetchProducts } from '../api/products'
import AppFooter from '../components/AppFooter.vue'
import AppHeader from '../components/AppHeader.vue'
import BaseSelect from '../components/BaseSelect.vue'
import ProductDrawer from '../components/ProductDrawer.vue'
import ProductGrid from '../components/ProductGrid.vue'
import { useFavorites } from '../composables/useFavorites'

const products = ref([])
const categories = ref([])
const ips = ref([])
const category = ref('')
const ip = ref('')
const sort = ref('')
const search = ref('')
const page = ref(1)
const pageSize = 24
const loading = ref(false)
const error = ref('')
const total = ref(0)
const selectedProduct = ref(null)
const { error: favoriteError, loadFavorites } = useFavorites()

const sortOptions = [
  { value: '', label: '默认' },
  { value: 'discount', label: '折扣' },
  { value: 'price', label: '价格' },
]
const categoryOptions = computed(() => [
  { value: '', label: '全部' },
  ...categories.value.map((item) => ({ value: String(item.item_id), label: item.name || String(item.item_id) })),
])
// 选项取 B 站首页抓下来的 IP 分区列表；筛选值仍是详情属性里的 IP 名，所以两边必须同名才筛得到。
const ipOptions = computed(() => [
  { value: '', label: '全部' },
  ...ips.value
    .filter((item) => item.name)
    .map((item) => ({ value: item.name, label: item.name })),
])

const totalPages = computed(() => Math.max(1, Math.ceil(total.value / pageSize)))
const pageNumbers = computed(() => {
  const start = Math.max(1, Math.min(page.value - 2, totalPages.value - 4))
  return Array.from({ length: Math.min(5, totalPages.value) }, (_, index) => start + index)
})

/* 关键词只在请求发出的那一刻从输入框现取，不再缓存一份"已提交"的副本：缓存副本会带来
   两份状态，切下拉或翻页时发出去的关键词就可能比输入框里看到的更旧。打字本身不触发请求，
   回车、点搜索、切筛选和翻页才发。 */
async function loadProducts() {
  loading.value = true
  error.value = ''
  try {
    const data = await fetchProducts({ category: category.value, ip: ip.value, search: search.value.trim(), sort: sort.value, limit: pageSize, offset: (page.value - 1) * pageSize })
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
  resetAndLoad()
}

async function loadCatalogOptions(filterType, target) {
  try {
    const data = await fetchCatalog(filterType)
    target.value = data.items || []
  } catch {
    target.value = []
  }
}

onMounted(() => {
  loadProducts()
  loadCatalogOptions('category', categories)
  loadCatalogOptions('ip', ips)
  loadFavorites()
})
watch([category, ip, sort], resetAndLoad)
</script>

<template>
  <main class="page-shell">
    <AppHeader />

    <div class="search-filter-row">
      <section id="products" class="search-section" aria-label="商品筛选">
        <span class="filter-label">搜索商品</span>
        <form class="search-bar" @submit.prevent="submitSearch">
          <div class="search-field search-field-main">
            <input v-model="search" aria-label="搜索商品名称" placeholder="输入商品名称，空格分隔多个关键词" />
          </div>
          <button class="search-orb" type="submit" aria-label="搜索" :disabled="loading"><Search :size="20" :stroke-width="2.2" aria-hidden="true" /></button>
        </form>
      </section>

      <div class="filter-row" aria-label="商品筛选">
        <BaseSelect v-model="category" class="category-filter" label="分类" :options="categoryOptions" />
        <BaseSelect v-model="ip" class="ip-filter" label="IP 分类" :options="ipOptions" />
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

    <ProductGrid :products="products" :loading="loading" :error="error || favoriteError" empty-title="没有找到匹配的商品" empty-hint="试试其他关键词或切换商品分类" @open="selectedProduct = $event" @retry="loadProducts" />

    <nav v-if="total > 0" class="pagination" aria-label="分页">
      <button class="pagination-arrow" type="button" :disabled="page === 1 || loading" aria-label="上一页" @click="page--; loadProducts()"><ChevronLeft :size="18" :stroke-width="1.8" aria-hidden="true" /></button>
      <button v-for="number in pageNumbers" :key="number" type="button" :class="{ active: number === page }" :disabled="loading" @click="page = number; loadProducts()">{{ number }}</button>
      <span class="page-total">{{ page }} / {{ totalPages }}</span>
      <button class="pagination-arrow" type="button" :disabled="page === totalPages || loading" aria-label="下一页" @click="page++; loadProducts()"><ChevronRight :size="18" :stroke-width="1.8" aria-hidden="true" /></button>
    </nav>

    <ProductDrawer v-if="selectedProduct" :product="selectedProduct" :key="selectedProduct.cluster_id" @close="selectedProduct = null" />
    <AppFooter />
  </main>
</template>

<style scoped>
.page-shell { width: min(1280px, calc(100% - 64px)); margin: 0 auto; padding-bottom: 64px; }
.section-kicker { margin: 0 0 12px; color: var(--color-text-muted); font-size: var(--fs-11); font-weight: 700; letter-spacing: 1.2px; line-height: 1.3; text-transform: uppercase; }
/* Two bands, not one row: DESIGN.md fixes the search pill at 64px and the dense application
   controls at 48px, so side by side their boxes would sit 8px out of step against each other
   and their labels on two different baselines. Stacked, each band keeps its documented height. */
.search-filter-row { display: flex; flex-direction: column; align-items: stretch; gap: 24px; width: 100%; margin: 48px auto 0; }
.search-section { display: flex; min-width: 0; flex-direction: column; align-items: stretch; gap: 8px; }
.search-bar { display: flex; flex: 0 0 64px; height: 64px; align-items: center; padding: 0 19px; border: 2px solid transparent; border-radius: 9999px; background: var(--color-surface); box-shadow: var(--shadow-card); transition: border-color var(--duration-fast) var(--ease-standard); }
/* The pill is the control, so states land on its border and the inner input must never draw its
   own box (DESIGN.md "Search pill states"). The 2px border is always present and transparent —
   `background-clip` defaults to border-box, so the white surface still fills it and the hairline
   from the shadow tier stays visible at rest. Focus only recolors it, so nothing — the typed
   text, the orb, the box itself — moves by a single pixel. */
.search-bar:hover { border-color: var(--color-border-strong); }
.search-bar:has(.search-field input:focus) { border-color: var(--color-focus); }
.search-field { display: flex; min-width: 0; flex-direction: column; align-items: flex-start; justify-content: center; gap: 4px; }
.search-field-main { flex: 1; }
.search-field input { width: 100%; padding: 0; overflow: hidden; border: 0; outline: 0; background: transparent; color: var(--color-text-muted); font-size: var(--fs-14); line-height: 1.43; text-overflow: ellipsis; white-space: nowrap; }
.search-field input:focus { color: var(--color-text-primary); }
.search-field input::placeholder { color: var(--color-text-disabled); opacity: 1; }
.search-orb { display: grid; flex: 0 0 46px; width: 46px; height: 46px; padding: 0; place-items: center; border: 0; border-radius: 50%; background: var(--color-accent); color: var(--color-on-accent); cursor: pointer; }
.search-orb:hover, .search-orb:focus-visible { background: var(--color-accent-hover); }
.search-orb:focus-visible { outline: 2px solid var(--color-on-accent); outline-offset: -4px; }
.search-orb:active { background: var(--color-accent-hover); }
.search-orb:disabled { background: var(--color-accent-disabled); color: var(--color-on-accent-disabled); cursor: not-allowed; }
.filter-row { display: flex; align-items: flex-start; gap: 24px; width: 100%; min-width: 0; }
.category-filter, .ip-filter { flex: 0 0 200px; min-width: 0; }
/* The sort group anchors the right edge, echoing the space-between rhythm of .results-heading. */
.sort-filter { display: flex; min-width: 0; flex-direction: column; align-items: flex-start; gap: 8px; margin-left: auto; }
.filter-label { color: var(--color-text-primary); font-size: var(--fs-13); font-weight: 600; }
.sort-options { display: flex; gap: 4px; padding: 4px; border-radius: 32px; background: var(--color-surface-soft); }
.sort-option { min-height: 40px; padding: 0 18px; border: 0; border-radius: 9999px; background: transparent; color: var(--color-text-muted); font-size: var(--fs-14); cursor: pointer; }
.sort-option:hover, .sort-option:focus-visible { color: var(--color-text-primary); }
.sort-option:focus-visible { outline: 2px solid var(--color-focus); outline-offset: 2px; }
.sort-option.active { background: var(--color-surface); color: var(--color-text-primary); box-shadow: var(--shadow-card); font-weight: 500; }
.sort-option:disabled { color: var(--color-text-disabled); cursor: not-allowed; opacity: .65; }
.results-heading { display: flex; align-items: center; justify-content: space-between; margin: 40px 0 24px; }
.results-heading h2 { margin: 0; color: var(--color-text-primary); font-size: var(--fs-22); font-weight: 500; letter-spacing: -.44px; line-height: 1.18; }
.result-count { margin: 20px 0 0; color: var(--color-text-muted); font-size: var(--fs-14); }
.pagination { display: flex; align-items: center; justify-content: center; gap: 8px; margin-top: 48px; color: var(--color-text-muted); }
.pagination button { display: grid; min-width: 40px; height: 40px; padding: 0 8px; place-items: center; border: 0; border-radius: 50%; background: transparent; color: var(--color-text-primary); font-size: var(--fs-14); cursor: pointer; }
.pagination button:hover, .pagination button:focus-visible { background: var(--color-surface-strong); }
.pagination button.active { background: var(--color-text-primary); color: var(--color-canvas); }
.pagination button:disabled { color: var(--color-text-disabled); cursor: not-allowed; opacity: .55; }
.pagination button.pagination-arrow { border: 1px solid var(--color-border); }
.page-total { margin: 0 12px; font-size: var(--fs-13); }
@media (max-width: 1128px) {
  .page-shell { width: min(100% - 48px, 960px); }
}
@media (max-width: 744px) {
  .page-shell { width: min(100% - 32px, 560px); }
  .search-filter-row { margin-top: 32px; gap: 16px; }
  .search-bar { height: 56px; }
  .filter-row { align-items: stretch; flex-direction: column; gap: 16px; }
  .category-filter, .ip-filter { width: 100%; flex-basis: auto; }
  .sort-filter { margin-left: 0; }
  .sort-options { width: 100%; }
  .sort-option { flex: 1; padding: 0 12px; }
  .results-heading { margin-top: 32px; }
}
@media (max-width: 420px) {
  .page-shell { width: calc(100% - 24px); }
  /* Compact overrides reference the token they descend from, so a future scale change
     still reaches them; each value stays below its base token on purpose. */
  .search-field input { font-size: var(--fs-12); }
}
@media (prefers-reduced-motion: reduce) {
  *, *::before, *::after { animation-duration: .01ms !important; animation-iteration-count: 1 !important; transition-duration: .01ms !important; }
}
</style>
