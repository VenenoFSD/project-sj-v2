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

export function listSchedules() {
  return fetchJson('/schedules')
}

export function createSchedule(payload) {
  return fetchJson('/schedules', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  })
}

export function updateSchedule(scheduleId, payload) {
  return fetchJson(`/schedules/${encodeURIComponent(scheduleId)}`, {
    method: 'PATCH',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  })
}

export function runSchedule(scheduleId) {
  return fetchJson(`/schedules/${encodeURIComponent(scheduleId)}/run`, { method: 'POST' })
}

export function deleteSchedule(scheduleId) {
  return fetchJson(`/schedules/${encodeURIComponent(scheduleId)}`, { method: 'DELETE' })
}
