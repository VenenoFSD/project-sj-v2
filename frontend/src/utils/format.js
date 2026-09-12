/**
 * 价格与图片的展示格式化。
 *
 * 商品卡片、价格行和详情抽屉渲染同一套价格/折扣/图片地址规则，所以这些纯函数集中在这里，
 * 由组件导入；不放 composable（无状态）也不放 api/（不发请求）。
 */

export function formatPrice(value) {
  return value === null || value === undefined ? '暂无价格' : `¥${Number(value).toFixed(2)}`
}

export function parsePriceValue(value) {
  if (value === null || value === undefined) return null
  const match = String(value).replace(/,/g, '').match(/-?\d+(?:\.\d+)?/)
  return match ? Number(match[0]) : null
}

export function formatDiscount(currentPrice, referencePrice) {
  const current = parsePriceValue(currentPrice)
  const reference = parsePriceValue(referencePrice)
  if (!Number.isFinite(current) || !Number.isFinite(reference) || current < 0 || reference <= 0 || current >= reference) return ''
  const discount = Math.round((current / reference) * 100) / 10
  return `${discount.toFixed(1).replace(/\.0$/, '')}折`
}

export function normalizeImageUrl(value) {
  if (!value) return ''
  if (value.startsWith('//')) return `https:${value}`
  if (value.startsWith('http://')) return value.replace('http://', 'https://')
  return value
}
