const API_BASE = import.meta.env.VITE_API_BASE || '/api'

export async function fetchProducts({ category, search, limit, offset }) {
  const params = new URLSearchParams({ limit: String(limit), offset: String(offset) })
  if (category) params.set('category', category)
  if (search) params.set('search', search)
  const response = await fetch(`${API_BASE}/products?${params}`)
  if (!response.ok) throw new Error(`加载商品失败（${response.status}）`)
  return response.json()
}

async function fetchJson(path) {
  const response = await fetch(`${API_BASE}${path}`)
  if (!response.ok) throw new Error(`请求失败（${response.status}）`)
  return response.json()
}

export function fetchProductDetails(clusterId) {
  return fetchJson(`/products/${encodeURIComponent(clusterId)}/details`)
}

export function fetchProductHistory(clusterId, limit = 30) {
  return fetchJson(`/products/${encodeURIComponent(clusterId)}/history?limit=${limit}`)
}

export function fetchProductDeals(clusterId, limit = 50) {
  return fetchJson(`/products/${encodeURIComponent(clusterId)}/deals?limit=${limit}`)
}

export function fetchProductPricePoints(clusterId, limit = 200) {
  return fetchJson(`/products/${encodeURIComponent(clusterId)}/price-points?limit=${limit}`)
}
