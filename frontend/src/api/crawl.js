const API_BASE = import.meta.env.VITE_API_BASE || '/api'

function getErrorMessage(payload, status) {
  if (typeof payload?.detail === 'string') return payload.detail
  if (payload?.detail) return JSON.stringify(payload.detail)
  return `请求失败（${status}）`
}

async function fetchJson(path, options = {}) {
  const response = await fetch(`${API_BASE}${path}`, options)
  const payload = await response.json().catch(() => null)
  if (!response.ok) throw new Error(getErrorMessage(payload, response.status))
  return payload
}

export function startCrawl(payload) {
  return fetchJson('/crawl-runs', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  })
}

export function getCrawlTask(taskId) {
  return fetchJson(`/crawl-runs/tasks/${encodeURIComponent(taskId)}`)
}
