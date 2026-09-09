<script setup>
import { computed, nextTick, onActivated, onBeforeUnmount, onDeactivated, onMounted, ref, watch } from 'vue'
import { Moon, Play, Sun } from 'lucide-vue-next'
import { getCrawlTask, startCrawl } from '../api/crawl'
import BaseSelect from '../components/BaseSelect.vue'

defineOptions({ name: 'BackendView' })

const form = ref({
  pages: 0,
  category: '142',
  ip: '',
  sort: 'hot',
  detail: true,
  no_alert: true,
})
const submitting = ref(false)
const taskId = ref('')
const task = ref(null)
const error = ref('')
const pollTimer = ref(null)
const pollInFlight = ref(false)
const taskOutputElement = ref(null)
const theme = ref('light')
const themeStorageKey = 'sj-select-theme'
const sortOptions = [
  { value: 'hot', label: '热门' },
  { value: 'mostListings', label: '发布量' },
  { value: 'priceFirst', label: '价格优先' },
]

const isRunning = computed(() => task.value?.status === 'running')
const statusLabel = computed(() => ({
  running: '运行中',
  success: '已完成',
  failed: '执行失败',
}[task.value?.status] || '等待中'))
const statusTone = computed(() => task.value?.status || 'pending')

function applyTheme(nextTheme, persist = false) {
  theme.value = nextTheme
  document.documentElement.dataset.theme = nextTheme
  if (persist) {
    try {
      window.localStorage.setItem(themeStorageKey, nextTheme)
    } catch {
      return
    }
  }
}

function initializeTheme() {
  let storedTheme = 'light'
  try {
    storedTheme = window.localStorage.getItem(themeStorageKey) || 'light'
  } catch {
    storedTheme = 'light'
  }
  applyTheme(storedTheme === 'dark' ? 'dark' : 'light')
}

function toggleTheme() {
  applyTheme(theme.value === 'dark' ? 'light' : 'dark', true)
}

function stopPolling() {
  if (pollTimer.value) {
    window.clearInterval(pollTimer.value)
    pollTimer.value = null
  }
}

function scrollTaskOutputToBottom() {
  if (taskOutputElement.value) taskOutputElement.value.scrollTop = taskOutputElement.value.scrollHeight
}

async function pollTask() {
  if (!taskId.value || pollInFlight.value) return
  pollInFlight.value = true
  try {
    task.value = await getCrawlTask(taskId.value)
    error.value = ''
    if (task.value.status !== 'running') stopPolling()
  } catch (err) {
    error.value = err.message || '任务状态获取失败'
    stopPolling()
  } finally {
    pollInFlight.value = false
  }
}

function startPolling() {
  stopPolling()
  void pollTask()
  pollTimer.value = window.setInterval(pollTask, 2000)
}

async function submitCrawl() {
  if (submitting.value || isRunning.value) return
  submitting.value = true
  error.value = ''
  stopPolling()
  task.value = null
  taskId.value = ''
  try {
    const result = await startCrawl({
      pages: Number(form.value.pages),
      category: form.value.category.trim() || null,
      ip: form.value.ip.trim() || null,
      sort: form.value.sort,
      detail: form.value.detail,
      no_alert: form.value.no_alert,
    })
    taskId.value = result.task_id
    task.value = result
    startPolling()
  } catch (err) {
    error.value = err.message || '爬取任务启动失败'
  } finally {
    submitting.value = false
  }
}

onMounted(initializeTheme)
watch(() => task.value?.output, () => nextTick(scrollTaskOutputToBottom))
onActivated(() => {
  initializeTheme()
  if (isRunning.value && taskId.value && !pollTimer.value) startPolling()
})
onDeactivated(stopPolling)
onBeforeUnmount(stopPolling)
</script>

<template>
  <main class="backend-page">
    <header class="backend-nav">
      <RouterLink class="brand" to="/" aria-label="返回首页">
        <span class="brand-mark">S</span>
        <span class="brand-name">SJ Select</span>
      </RouterLink>
      <div class="backend-nav-actions">
        <RouterLink class="back-link" to="/">首页</RouterLink>
        <button class="theme-toggle" type="button" :aria-label="theme === 'dark' ? '切换到浅色主题' : '切换到深色主题'" :title="theme === 'dark' ? '切换到浅色主题' : '切换到深色主题'" @click="toggleTheme">
          <Sun v-if="theme === 'dark'" :size="18" :stroke-width="1.8" aria-hidden="true" />
          <Moon v-else :size="18" :stroke-width="1.8" aria-hidden="true" />
        </button>
      </div>
    </header>

    <section class="backend-intro" aria-labelledby="backend-title">
      <p class="section-kicker">OPERATIONS</p>
      <h1 id="backend-title">后台</h1>
      <p>配置并启动一次商品数据爬取，任务日志会在下方持续更新。</p>
    </section>

    <div class="backend-sections">
      <section class="control-card" aria-labelledby="crawl-form-title">
        <div class="section-heading">
          <div>
            <p class="section-kicker">CRAWL CONFIGURATION</p>
            <h2 id="crawl-form-title">启动爬取</h2>
          </div>
          <span class="section-index">01</span>
        </div>

        <form class="crawl-form" @submit.prevent="submitCrawl">
          <label>
            <span>抓取页数</span>
            <input v-model.number="form.pages" type="number" min="0" max="500" required />
            <small>0 表示全量抓取</small>
          </label>
          <label>
            <span>商品分类</span>
            <input v-model="form.category" type="text" placeholder="例如 898" />
            <small>留空表示全部分类</small>
          </label>
          <label>
            <span>IP 分区</span>
            <input v-model="form.ip" type="text" placeholder="可选" />
            <small>留空表示不限制</small>
          </label>
          <BaseSelect v-model="form.sort" label="排序方式" hint="对应爬虫排序参数" :options="sortOptions" />
          <div class="form-options">
            <label class="checkbox-label"><input v-model="form.detail" type="checkbox" /><span>获取商品详情</span></label>
            <label class="checkbox-label"><input v-model="form.no_alert" type="checkbox" /><span>关闭价格异动检测</span></label>
          </div>
          <div class="form-actions">
            <p>任务将在后台异步执行，启动后可查看实时输出。</p>
            <button class="primary-button" type="submit" :disabled="submitting || isRunning">
              <Play :size="16" :stroke-width="2" aria-hidden="true" />
              <span>{{ submitting ? '正在启动…' : isRunning ? '任务运行中' : '开始爬取' }}</span>
            </button>
          </div>
        </form>
      </section>

      <section class="status-card" aria-labelledby="crawl-status-title">
        <div class="section-heading">
          <div>
            <p class="section-kicker">TASK MONITOR</p>
            <h2 id="crawl-status-title">任务状态</h2>
          </div>
          <span class="section-index">02</span>
        </div>

        <p v-if="error" class="error-message" role="alert">{{ error }}</p>
        <div v-if="!task" class="status-empty">
          <span class="empty-mark">—</span>
          <strong>暂无运行中的任务</strong>
          <span>提交上方表单后，这里会显示任务状态与爬虫输出。</span>
        </div>
        <template v-else>
          <div class="status-summary">
            <div class="status-main">
              <span class="status-dot" :class="statusTone"></span>
              <strong class="status-pill" :class="statusTone">{{ statusLabel }}</strong>
              <span class="task-id">{{ task.task_id }}</span>
            </div>
            <span class="polling-label">{{ isRunning ? '每 2 秒自动更新' : '轮询已停止' }}</span>
          </div>
          <div class="task-facts">
            <div><span>进程 ID</span><strong>{{ task.pid || '—' }}</strong></div>
            <div><span>返回码</span><strong>{{ task.return_code ?? '—' }}</strong></div>
          </div>
          <div class="output-heading"><span>执行输出</span><span>{{ task.output ? 'LIVE OUTPUT' : 'WAITING' }}</span></div>
          <pre ref="taskOutputElement" class="task-output">{{ task.output || '任务已启动，等待爬虫输出…' }}</pre>
        </template>
      </section>
    </div>
  </main>
</template>

<style scoped>
:global(*) { box-sizing: border-box; }
:global(:root) {
  color-scheme: light;
  --color-canvas: #fff;
  --color-surface: #fff;
  --color-surface-soft: #f7f7f7;
  --color-surface-strong: #f2f2f2;
  --color-text-primary: #222;
  --color-text-secondary: #3f3f3f;
  --color-text-muted: #6a6a6a;
  --color-text-disabled: #929292;
  --color-border: #ddd;
  --color-border-soft: #ebebeb;
  --color-border-strong: #c1c1c1;
  --color-accent: #ff385c;
  --color-accent-hover: #e00b41;
  --color-accent-disabled: #ffd1da;
  --color-on-accent: #fff;
  --color-on-accent-disabled: #fff;
  --color-error: #c13515;
  --color-error-surface: #fff4f2;
  --color-focus: #222;
  --shadow-card: rgba(0, 0, 0, .02) 0 0 0 1px, rgba(0, 0, 0, .04) 0 2px 6px, rgba(0, 0, 0, .1) 0 4px 8px;
}
:global(:root[data-theme="dark"]) {
  color-scheme: dark;
  --color-canvas: #151515;
  --color-surface: #1d1d1d;
  --color-surface-soft: #242424;
  --color-surface-strong: #2c2c2c;
  --color-text-primary: #f5f5f5;
  --color-text-secondary: #dedede;
  --color-text-muted: #ababab;
  --color-text-disabled: #777;
  --color-border: #3b3b3b;
  --color-border-soft: #2d2d2d;
  --color-border-strong: #5a5a5a;
  --color-accent: #ff5470;
  --color-accent-hover: #ff7188;
  --color-accent-disabled: #713847;
  --color-on-accent: #fff;
  --color-on-accent-disabled: #fff;
  --color-error: #ff8a65;
  --color-error-surface: #3a211d;
  --color-focus: #fff;
  --shadow-card: rgba(255, 255, 255, .07) 0 0 0 1px, rgba(0, 0, 0, .28) 0 4px 12px;
}
:global(body) { margin: 0; background: var(--color-canvas); color: var(--color-text-primary); font-family: "Airbnb Cereal VF", Circular, Inter, -apple-system, system-ui, Roboto, "Helvetica Neue", sans-serif; }
:global(button), :global(input), :global(select) { font: inherit; }
:global(button), :global(a) { -webkit-tap-highlight-color: transparent; }
.backend-page { width: min(1120px, calc(100% - 64px)); margin: 0 auto; padding-bottom: 64px; }
.backend-nav { position: relative; display: flex; align-items: center; justify-content: space-between; height: 80px; border-bottom: 1px solid var(--color-border-soft); }
.brand { display: flex; align-items: center; gap: 9px; color: var(--color-text-primary); font-size: 16px; font-weight: 600; text-decoration: none; }
.brand-mark { display: grid; width: 32px; height: 32px; place-items: center; border-radius: 50%; background: var(--color-accent); color: var(--color-on-accent); font-size: 18px; font-weight: 700; }
.backend-nav-actions { display: flex; align-items: center; gap: 20px; }
.back-link { color: var(--color-text-muted); font-size: 14px; text-decoration: none; }
.back-link:hover, .back-link:focus-visible { color: var(--color-text-primary); text-decoration: underline; text-underline-offset: 4px; }
.theme-toggle { display: grid; width: 40px; height: 40px; padding: 0; place-items: center; border: 1px solid var(--color-border); border-radius: 50%; background: var(--color-surface); color: var(--color-text-primary); cursor: pointer; }
.theme-toggle:hover, .theme-toggle:focus-visible { background: var(--color-surface-strong); box-shadow: var(--shadow-card); }
.backend-intro { padding: 64px 0 40px; }
.section-kicker { margin: 0 0 8px; color: var(--color-accent); font-size: 11px; font-weight: 700; letter-spacing: 1.2px; line-height: 1.3; }
.backend-intro h1 { margin: 0; color: var(--color-text-primary); font-size: 36px; font-weight: 600; letter-spacing: -.6px; line-height: 1.2; }
.backend-intro > p:last-child { margin: 12px 0 0; color: var(--color-text-muted); font-size: 15px; line-height: 1.5; }
.backend-sections { display: grid; gap: 24px; }
.control-card, .status-card { padding: 32px; border: 1px solid var(--color-border-soft); border-radius: 14px; background: var(--color-surface); }
.section-heading { display: flex; align-items: flex-start; justify-content: space-between; gap: 16px; margin-bottom: 28px; }
.section-heading .section-kicker { margin-bottom: 6px; color: var(--color-text-muted); font-size: 10px; }
.section-heading h2 { margin: 0; color: var(--color-text-primary); font-size: 22px; font-weight: 500; letter-spacing: -.44px; line-height: 1.2; }
.section-index { color: var(--color-text-disabled); font-size: 12px; font-weight: 600; }
.crawl-form { display: grid; grid-template-columns: repeat(4, minmax(0, 1fr)); gap: 24px 16px; }
.crawl-form label:not(.checkbox-label) { display: flex; flex-direction: column; gap: 8px; }
.crawl-form label > span:first-child { color: var(--color-text-primary); font-size: 13px; font-weight: 600; }
.crawl-form input[type="number"], .crawl-form input[type="text"], .crawl-form select { width: 100%; height: 48px; padding: 0 14px; border: 1px solid var(--color-border); border-radius: 8px; outline: 0; background: var(--color-surface); color: var(--color-text-primary); font-size: 14px; }
.crawl-form input::placeholder { color: var(--color-text-disabled); }
.crawl-form input[type="number"]:focus, .crawl-form input[type="text"]:focus, .crawl-form select:focus { border: 2px solid var(--color-focus); }
.crawl-form small { min-height: 16px; color: var(--color-text-disabled); font-size: 12px; line-height: 1.3; }
.form-options { display: flex; grid-column: 1 / -1; gap: 24px; padding-top: 4px; border-top: 1px solid var(--color-border-soft); }
.checkbox-label { display: inline-flex; flex-direction: row !important; align-items: center; gap: 8px !important; padding-top: 20px; color: var(--color-text-secondary); font-size: 13px; cursor: pointer; }
.checkbox-label input { width: 16px; height: 16px; accent-color: var(--color-accent); }
.form-actions { display: flex; grid-column: 1 / -1; align-items: center; justify-content: space-between; gap: 20px; padding-top: 8px; }
.form-actions p { margin: 0; color: var(--color-text-muted); font-size: 13px; }
.primary-button { display: inline-flex; min-width: 132px; height: 48px; align-items: center; justify-content: center; gap: 8px; padding: 0 20px; border: 0; border-radius: 8px; background: var(--color-accent); color: var(--color-on-accent); font-size: 14px; font-weight: 500; cursor: pointer; }
.primary-button:hover, .primary-button:focus-visible { background: var(--color-accent-hover); }
.primary-button:disabled { background: var(--color-accent-disabled); color: var(--color-on-accent-disabled); cursor: not-allowed; }
.error-message { margin: 0 0 24px; padding: 12px 14px; border-radius: 8px; background: var(--color-error-surface); color: var(--color-error); font-size: 13px; }
.status-empty { display: flex; min-height: 180px; flex-direction: column; align-items: center; justify-content: center; gap: 8px; color: var(--color-text-muted); text-align: center; }
.empty-mark { display: grid; width: 42px; height: 42px; margin-bottom: 4px; place-items: center; border-radius: 50%; background: var(--color-surface-strong); color: var(--color-text-disabled); font-size: 24px; }
.status-empty strong { color: var(--color-text-primary); font-size: 16px; font-weight: 600; }
.status-empty span:last-child { font-size: 13px; }
.status-summary { display: flex; align-items: center; justify-content: space-between; gap: 16px; padding: 16px; border-radius: 8px; background: var(--color-surface-soft); }
.status-main { display: flex; min-width: 0; align-items: center; gap: 10px; }
.status-dot { width: 8px; height: 8px; flex: 0 0 auto; border-radius: 50%; background: var(--color-text-disabled); }
.status-dot.running { background: var(--color-accent); box-shadow: 0 0 0 4px color-mix(in srgb, var(--color-accent) 16%, transparent); }
.status-dot.success { background: #2f9e69; }
.status-dot.failed { background: var(--color-error); }
.status-pill { color: var(--color-text-primary); font-size: 14px; font-weight: 600; }
.status-pill.success { color: #2f9e69; }
.status-pill.failed { color: var(--color-error); }
.task-id { overflow: hidden; color: var(--color-text-disabled); font-family: ui-monospace, SFMono-Regular, Consolas, monospace; font-size: 11px; text-overflow: ellipsis; white-space: nowrap; }
.polling-label { flex: 0 0 auto; color: var(--color-text-muted); font-size: 12px; }
.task-facts { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 12px; margin-top: 16px; }
.task-facts div { display: flex; align-items: baseline; justify-content: space-between; gap: 12px; padding-bottom: 12px; border-bottom: 1px solid var(--color-border-soft); color: var(--color-text-muted); font-size: 13px; }
.task-facts strong { color: var(--color-text-primary); font-weight: 500; }
.output-heading { display: flex; align-items: center; justify-content: space-between; gap: 16px; margin-top: 24px; color: var(--color-text-primary); font-size: 13px; font-weight: 600; }
.output-heading span:last-child { color: var(--color-text-disabled); font-size: 10px; letter-spacing: 1px; }
.task-output { min-height: 180px; max-height: 360px; margin: 12px 0 0; padding: 16px; overflow: auto; border-radius: 8px; background: var(--color-surface-soft); color: var(--color-text-secondary); font-family: ui-monospace, SFMono-Regular, Consolas, monospace; font-size: 12px; line-height: 1.6; white-space: pre-wrap; word-break: break-word; }
@media (max-width: 744px) {
  .backend-page { width: min(100% - 32px, 560px); }
  .backend-nav { height: 64px; }
  .brand-name { display: none; }
  .backend-nav-actions { gap: 12px; }
  .backend-intro { padding: 48px 0 32px; }
  .backend-intro h1 { font-size: 30px; }
  .control-card, .status-card { padding: 24px 20px; }
  .crawl-form { grid-template-columns: repeat(2, minmax(0, 1fr)); }
  .form-actions { align-items: stretch; flex-direction: column; }
  .primary-button { width: 100%; }
  .status-summary { align-items: flex-start; flex-direction: column; }
  .polling-label { padding-left: 18px; }
}
@media (max-width: 420px) {
  .backend-page { width: calc(100% - 24px); }
  .crawl-form { display: block; }
  .crawl-form > label { margin-bottom: 18px; }
  .form-options { display: grid; gap: 0; }
  .form-actions { margin-top: 20px; }
  .task-facts { display: block; }
  .task-facts div + div { margin-top: 12px; }
}
</style>
