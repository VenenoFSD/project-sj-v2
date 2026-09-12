const API_BASE = import.meta.env.VITE_API_BASE || '/api'

// 目前没有登录，user_id 走后端默认值 `default`，前端不传这个参数。
export async function fetchFavorites() {
  const response = await fetch(`${API_BASE}/favorites`)
  if (!response.ok) throw new Error(`加载收藏失败（${response.status}）`)
  return response.json()
}

export async function addFavorite(clusterId) {
  const response = await fetch(`${API_BASE}/favorites/${encodeURIComponent(clusterId)}`, { method: 'POST' })
  if (!response.ok) throw new Error(`收藏失败（${response.status}）`)
  return response.json()
}

export async function removeFavorite(clusterId) {
  const response = await fetch(`${API_BASE}/favorites/${encodeURIComponent(clusterId)}`, { method: 'DELETE' })
  if (!response.ok) throw new Error(`取消收藏失败（${response.status}）`)
  return response.json()
}
