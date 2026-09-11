<script setup>
defineOptions({ name: 'AppFooter' })

const columns = [
  {
    title: '商品',
    links: [
      { label: '热门商品', to: '/products' },
      { label: '分类浏览', to: '/products' },
    ],
  },
  {
    title: '后台',
    links: [
      { label: '即时任务', to: '/backend/instant' },
      { label: '定时任务', to: '/backend/scheduled' },
    ],
  },
  {
    title: '资源',
    links: [
      { label: 'API 文档', to: '/docs/api' },
      { label: '爬虫文档', to: '/docs/crawler' },
    ],
  },
]

const year = new Date().getFullYear()
</script>

<template>
  <footer class="app-footer">
    <div class="footer-inner">
      <div class="footer-columns">
        <section v-for="column in columns" :key="column.title" class="footer-column">
          <h3>{{ column.title }}</h3>
          <ul>
            <li v-for="link in column.links" :key="link.label">
              <RouterLink :to="link.to" class="footer-link">{{ link.label }}</RouterLink>
            </li>
          </ul>
        </section>
      </div>
      <div class="legal-band">
        <span>© {{ year }} SJ Select · 商品价格追踪</span>
        <span class="legal-meta">数据来源：哔哩哔哩会员购</span>
      </div>
    </div>
  </footer>
</template>

<style scoped>
.app-footer { margin-top: 64px; border-top: 1px solid var(--color-border-soft); background: var(--color-canvas); }
.footer-inner { width: min(1280px, calc(100% - 64px)); margin: 0 auto; padding: 48px 0 24px; }
.footer-columns { display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: 24px; }
.footer-column h3 { margin: 0 0 16px; color: var(--color-text-primary); font-size: var(--fs-16); font-weight: 500; line-height: 1.25; }
.footer-column ul { display: flex; flex-direction: column; gap: 12px; margin: 0; padding: 0; list-style: none; }
.footer-link { color: var(--color-text-primary); font-size: var(--fs-14); font-weight: 400; line-height: 1.43; text-decoration: none; }
.footer-link:hover, .footer-link:focus-visible { text-decoration: underline; text-underline-offset: 4px; }
.legal-band { display: flex; align-items: center; justify-content: space-between; gap: 16px; margin-top: 48px; padding-top: 16px; border-top: 1px solid var(--color-border-soft); color: var(--color-text-muted); font-size: var(--fs-13); line-height: 1.23; }
.legal-meta { color: var(--color-text-disabled); }
@media (max-width: 744px) {
  .footer-inner { width: min(100% - 32px, 560px); padding: 32px 0 20px; }
  .footer-columns { grid-template-columns: 1fr; gap: 20px; }
  .legal-band { flex-direction: column; align-items: flex-start; gap: 8px; margin-top: 32px; }
}
@media (max-width: 420px) {
  .footer-inner { width: calc(100% - 24px); }
}
</style>
