const API_BASE = import.meta.env.VITE_API_BASE || '/api'

export async function fetchCatalog(filterType) {
  const response = await fetch(`${API_BASE}/catalog/${encodeURIComponent(filterType)}`)
  if (!response.ok) throw new Error(`目录请求失败：${response.status}`)
  return response.json()
}
