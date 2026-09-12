import { ref } from 'vue'
import { addFavorite, fetchFavorites, removeFavorite } from '../api/favorites'

/**
 * 收藏状态的唯一来源。
 *
 * 商品页的心形、收藏页的列表和详情抽屉读的是同一份数据，所以状态放在模块作用域，
 * 由 `useFavorites()` 统一暴露；请求本身留在 `frontend/src/api/favorites.js`。
 *
 * `favoriteIds` 只服务心形高亮，点击后立即翻转、失败再回滚（乐观更新），这样慢网络下
 * 点击不会像没反应。`favorites` 是收藏页的列表数据，挂载时拉取。
 */

const favoriteIds = ref(new Set())
const favorites = ref([])
const pendingIds = ref(new Set())
const loading = ref(false)
const error = ref('')
let loaded = false

async function loadFavorites(force = false) {
  if (loaded && !force) return
  loading.value = true
  error.value = ''
  try {
    const data = await fetchFavorites()
    favorites.value = data.items || []
    favoriteIds.value = new Set(favorites.value.map((item) => item.product?.cluster_id).filter(Boolean))
    loaded = true
  } catch (err) {
    error.value = err.message || '加载收藏失败，请稍后重试'
  } finally {
    loading.value = false
  }
}

async function toggleFavorite(product) {
  const clusterId = product?.cluster_id
  if (!clusterId || pendingIds.value.has(clusterId)) return
  const wasFavorited = favoriteIds.value.has(clusterId)
  // 回滚用：数组整体替换，所以这里的旧引用在失败时可以直接还原。
  const previousFavorites = favorites.value

  error.value = ''
  pendingIds.value.add(clusterId)
  if (wasFavorited) {
    favoriteIds.value.delete(clusterId)
    favorites.value = favorites.value.filter((item) => item.product?.cluster_id !== clusterId)
  } else {
    favoriteIds.value.add(clusterId)
    favorites.value = [{ id: null, created_at: new Date().toISOString(), product }, ...favorites.value]
  }

  try {
    if (wasFavorited) await removeFavorite(clusterId)
    else await addFavorite(clusterId)
  } catch (err) {
    if (wasFavorited) favoriteIds.value.add(clusterId)
    else favoriteIds.value.delete(clusterId)
    favorites.value = previousFavorites
    error.value = err.message || '收藏操作失败，请稍后重试'
  } finally {
    pendingIds.value.delete(clusterId)
  }
}

export function useFavorites() {
  return {
    favorites,
    loading,
    error,
    loadFavorites,
    toggleFavorite,
    isFavorited: (clusterId) => favoriteIds.value.has(clusterId),
    isPending: (clusterId) => pendingIds.value.has(clusterId),
  }
}
