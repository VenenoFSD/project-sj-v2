<script setup>
import { computed, nextTick, onActivated, onBeforeUnmount, onDeactivated, onMounted, ref, watch } from 'vue'
import { useRoute } from 'vue-router'
import { CalendarClock, Check, Clock3, Edit3, LoaderCircle, Moon, Play, Plus, Power, PowerOff, RefreshCw, Sun, Trash2, X } from 'lucide-vue-next'
import { getCrawlTask, startCrawl } from '../api/crawl'
import { createSchedule, deleteSchedule, listSchedules, runSchedule, updateSchedule } from '../api/schedules'
import BaseSelect from '../components/BaseSelect.vue'
import AppFooter from '../components/AppFooter.vue'
import { applyStoredTheme, useTheme } from '../composables/useTheme'

defineOptions({ name: 'BackendView' })

const form = ref({
  pages: 0,
  category: '142',
  ip: '',
  sort: 'hot',
  detail: true,
  no_alert: true,
  no_overview: false,
})
const submitting = ref(false)
const taskId = ref('')
const task = ref(null)
const error = ref('')
const pollTimer = ref(null)
const pollInFlight = ref(false)
const taskOutputElement = ref(null)
const autoScroll = ref(true)
const scheduleAutoScroll = ref(true)
const { theme, toggleTheme } = useTheme()
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
const route = useRoute()
const activePanel = computed(() => route.name === 'backend-scheduled' ? 'scheduled' : 'instant')
const schedules = ref([])
const schedulesLoading = ref(false)
const schedulesLoaded = ref(false)
const scheduleError = ref('')
const scheduleNotice = ref('')
const selectedScheduleId = ref(null)
const scheduleTask = ref(null)
const schedulePollTimer = ref(null)
const schedulePollInFlight = ref(false)
const scheduleModalOpen = ref(false)
const scheduleModalMode = ref('create')
const scheduleSubmitting = ref(false)
const scheduleModalError = ref('')
const editingScheduleId = ref(null)
const scheduleForm = ref(createScheduleForm())

const selectedSchedule = computed(() => schedules.value.find((item) => item.id === selectedScheduleId.value) || null)
const runningSchedule = computed(() => schedules.value.find((item) => item.last_status === 'running') || null)
// The monitor panel always describes the explicitly selected task. It is never replaced by
// another task that happens to be running, so clicking a row can only ever show that row's
// run information. Picking a sensible default (the running task) is loadSchedules' job.
const monitoredSchedule = computed(() => selectedSchedule.value)
const scheduleStatusLabel = computed(() => ({
  running: '运行中',
  success: '已完成',
  failed: '执行失败',
  skipped: '已跳过',
  error: '配置错误',
}[monitoredSchedule.value?.last_status] || '尚未运行'))
const scheduleStatusTone = computed(() => monitoredSchedule.value?.last_status || 'pending')
const scheduleTaskRunning = computed(() => scheduleTask.value?.status === 'running')
const scheduleFormTitle = computed(() => scheduleModalMode.value === 'edit' ? '编辑定时任务' : '创建定时任务')

function createScheduleForm() {
  return {
    name: '',
    interval_seconds: 1800,
    pages: 0,
    category: '142',
    ip: '',
    sort: 'hot',
    detail: true,
    no_alert: true,
    no_overview: true,
  }
}

function stopPolling() {
  if (pollTimer.value) {
    window.clearInterval(pollTimer.value)
    pollTimer.value = null
  }
}

function scrollTaskOutputToBottom() {
  if (!autoScroll.value) return
  if (taskOutputElement.value) taskOutputElement.value.scrollTop = taskOutputElement.value.scrollHeight
}

function scrollScheduleOutputToBottom(force = false) {
  if (!scheduleAutoScroll.value) return
  const outputElement = document.querySelector('.schedule-output')
  if (!outputElement) return
  if (!force && scheduleTask.value?.status !== 'running') return
  outputElement.scrollTop = outputElement.scrollHeight
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
      no_overview: form.value.no_overview,
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

function normalizeSchedulePayload(source) {
  return {
    pages: Number(source.pages),
    category: source.category.trim() || null,
    ip: source.ip.trim() || null,
    sort: source.sort,
    detail: source.detail,
    no_alert: source.no_alert,
    no_overview: source.no_overview,
  }
}

function selectSchedule(schedule) {
  selectedScheduleId.value = schedule?.id ?? null
  scheduleTask.value = null
  // Selecting a task takes over polling: a running task keeps refreshing every 2.5s, while an
  // idle task fetches once and lets pollScheduleTask stop the timer by itself.
  startSchedulePolling()
}

function stopSchedulePolling() {
  if (schedulePollTimer.value) {
    window.clearInterval(schedulePollTimer.value)
    schedulePollTimer.value = null
  }
}

// Polling always targets the selected task and is only started when that task has a run to read;
// a task that never ran would otherwise keep a no-op timer alive forever.
function startSchedulePolling() {
  stopSchedulePolling()
  if (!monitoredSchedule.value?.last_task_id) return
  void pollScheduleTask()
  schedulePollTimer.value = window.setInterval(pollScheduleTask, 2500)
}

async function pollScheduleTask() {
  const schedule = monitoredSchedule.value
  if (!schedule?.last_task_id || schedulePollInFlight.value) return
  schedulePollInFlight.value = true
  try {
    scheduleTask.value = await getCrawlTask(schedule.last_task_id)
    if (scheduleTask.value.status === 'running') return
    // The run settled: stop following it, and pull the list once so the row's status, next run
    // time and the action-button state catch up with what the panel already shows.
    stopSchedulePolling()
    if (schedule.last_status === 'running') await refreshSchedules()
  } catch (err) {
    if (schedule.last_status === 'running') scheduleError.value = err.message || '定时任务状态获取失败'
    stopSchedulePolling()
  } finally {
    schedulePollInFlight.value = false
  }
}

// Refreshes list data only. Unlike loadSchedules it leaves selection and polling untouched, so
// calling it from the polling loop can never restart the timer and spin.
async function refreshSchedules() {
  try {
    const result = await listSchedules()
    schedules.value = result.items || []
    schedulesLoaded.value = true
  } catch (err) {
    scheduleError.value = err.message || '定时任务加载失败'
  }
}

async function loadSchedules(selectId = selectedScheduleId.value) {
  schedulesLoading.value = true
  scheduleError.value = ''
  try {
    const result = await listSchedules()
    schedules.value = result.items || []
    schedulesLoaded.value = true
    const preferred = schedules.value.find((item) => item.id === selectId)
      || schedules.value.find((item) => item.last_status === 'running')
      || schedules.value[0]
    selectedScheduleId.value = preferred?.id ?? null
    if (!preferred?.last_task_id) scheduleTask.value = null
    startSchedulePolling()
  } catch (err) {
    scheduleError.value = err.message || '定时任务加载失败'
  } finally {
    schedulesLoading.value = false
  }
}

function openCreateSchedule() {
  scheduleModalMode.value = 'create'
  editingScheduleId.value = null
  scheduleForm.value = createScheduleForm()
  scheduleModalError.value = ''
  scheduleModalOpen.value = true
}

function openEditSchedule(schedule) {
  const params = schedule.crawl_params || {}
  scheduleModalMode.value = 'edit'
  editingScheduleId.value = schedule.id
  scheduleForm.value = {
    name: schedule.name || '',
    interval_seconds: schedule.interval_seconds,
    pages: params.pages ?? 0,
    category: params.category || '',
    ip: params.ip || '',
    sort: params.sort || 'hot',
    detail: Boolean(params.detail),
    no_alert: Boolean(params.no_alert),
    no_overview: Boolean(params.no_overview),
  }
  scheduleModalError.value = ''
  scheduleModalOpen.value = true
}

function closeScheduleModal() {
  if (scheduleSubmitting.value) return
  scheduleModalOpen.value = false
}

function handleModalKeydown(event) {
  if (event.key === 'Escape' && scheduleModalOpen.value) {
    event.preventDefault()
    closeScheduleModal()
  }
}

async function submitSchedule() {
  if (scheduleSubmitting.value) return
  scheduleSubmitting.value = true
  scheduleModalError.value = ''
  const payload = {
    name: scheduleForm.value.name.trim() || null,
    interval_seconds: Number(scheduleForm.value.interval_seconds),
    crawl_params: normalizeSchedulePayload(scheduleForm.value),
  }
  try {
    if (scheduleModalMode.value === 'edit') {
      await updateSchedule(editingScheduleId.value, payload)
    } else {
      await createSchedule(payload)
    }
    scheduleModalOpen.value = false
    scheduleNotice.value = scheduleModalMode.value === 'edit' ? '定时任务已更新' : '定时任务已创建'
    await loadSchedules(editingScheduleId.value)
  } catch (err) {
    scheduleModalError.value = err.message || '定时任务保存失败'
  } finally {
    scheduleSubmitting.value = false
  }
}

async function toggleSchedule(schedule) {
  scheduleError.value = ''
  try {
    await updateSchedule(schedule.id, { enabled: !schedule.enabled })
    scheduleNotice.value = schedule.enabled ? '定时任务已停用' : '定时任务已启用'
    await loadSchedules(schedule.id)
  } catch (err) {
    scheduleError.value = err.message || '定时任务状态更新失败'
  }
}

async function triggerSchedule(schedule) {
  scheduleError.value = ''
  try {
    const result = await runSchedule(schedule.id)
    scheduleNotice.value = '定时任务已立即触发'
    selectedScheduleId.value = schedule.id
    scheduleTask.value = result
    await loadSchedules(schedule.id)
    startSchedulePolling()
  } catch (err) {
    scheduleError.value = err.message || '定时任务触发失败'
  }
}

async function removeSchedule(schedule) {
  if (!window.confirm(`确定删除定时任务“${schedule.name || `任务 ${schedule.id}`}”吗？`)) return
  scheduleError.value = ''
  try {
    await deleteSchedule(schedule.id)
    scheduleNotice.value = '定时任务已删除'
    if (selectedScheduleId.value === schedule.id) {
      selectedScheduleId.value = null
      scheduleTask.value = null
      stopSchedulePolling()
    }
    await loadSchedules()
  } catch (err) {
    scheduleError.value = err.message || '定时任务删除失败'
  }
}

function formatScheduleTime(value) {
  if (!value) return '—'
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return value
  return date.toLocaleString('zh-CN', { hour12: false })
}

function formatInterval(seconds) {
  if (!seconds) return '—'
  if (seconds % 86400 === 0) return `每 ${seconds / 86400} 天`
  if (seconds % 3600 === 0) return `每 ${seconds / 3600} 小时`
  if (seconds % 60 === 0) return `每 ${seconds / 60} 分钟`
  return `每 ${seconds} 秒`
}

function scheduleStatusText(status) {
  return ({
    running: '运行中',
    success: '已完成',
    failed: '执行失败',
    skipped: '已跳过',
    error: '配置错误',
  }[status] || '尚未运行')
}

function scheduleStatusClass(status) {
  return status || 'pending'
}

function isScheduleActionDisabled(schedule) {
  return schedulesLoading.value || scheduleTaskRunning.value || Boolean(runningSchedule.value && runningSchedule.value.id !== schedule.id)
}

// The backend refuses to run a disabled schedule with a 409, so "run now" is disabled for it as
// well. Enable/edit/delete stay available, since they are how a disabled task is revived.
function isScheduleTriggerDisabled(schedule) {
  return !schedule.enabled || isScheduleActionDisabled(schedule)
}

onMounted(() => {
  applyStoredTheme()
  window.addEventListener('keydown', handleModalKeydown)
})
watch(() => task.value?.output, () => nextTick(scrollTaskOutputToBottom))
watch(() => scheduleTask.value?.output, () => nextTick(scrollScheduleOutputToBottom))
// Re-enabling the toggle jumps to the latest output immediately, even after a task settled.
watch(autoScroll, (enabled) => { if (enabled) nextTick(scrollTaskOutputToBottom) })
watch(scheduleAutoScroll, (enabled) => { if (enabled) nextTick(() => scrollScheduleOutputToBottom(true)) })
watch(activePanel, (panel) => {
  if (panel === 'scheduled') {
    scheduleNotice.value = ''
    if (!schedulesLoaded.value) void loadSchedules()
    else startSchedulePolling()
  } else {
    stopSchedulePolling()
  }
})
onActivated(() => {
  applyStoredTheme()
  if (isRunning.value && taskId.value && !pollTimer.value) startPolling()
  if (activePanel.value === 'scheduled') {
    void loadSchedules()
  }
})
onDeactivated(stopPolling)
onBeforeUnmount(() => {
  stopPolling()
  stopSchedulePolling()
  window.removeEventListener('keydown', handleModalKeydown)
})
</script>

<template>
  <main class="backend-page">
    <header class="backend-nav">
      <RouterLink class="brand" to="/" aria-label="返回首页">
        <span class="brand-mark">S</span>
        <span class="brand-name">SJ Select</span>
      </RouterLink>
      <nav class="backend-page-nav" aria-label="后台任务导航">
        <RouterLink class="backend-page-tab" :class="{ active: activePanel === 'instant' }" to="/backend/instant" :aria-current="activePanel === 'instant' ? 'page' : undefined">
          <span class="backend-page-tab-icon"><Play :size="20" :stroke-width="1.8" aria-hidden="true" /></span>
          <span>即时任务</span>
        </RouterLink>
        <RouterLink class="backend-page-tab" :class="{ active: activePanel === 'scheduled' }" to="/backend/scheduled" :aria-current="activePanel === 'scheduled' ? 'page' : undefined">
          <span class="backend-page-tab-icon"><CalendarClock :size="20" :stroke-width="1.8" aria-hidden="true" /></span>
          <span>定时任务</span>
        </RouterLink>
      </nav>
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
      <h1 id="backend-title">{{ activePanel === 'instant' ? '即时任务' : '定时任务' }}</h1>
      <p>{{ activePanel === 'instant' ? '配置并启动一次商品数据爬取，任务日志会在下方持续更新。' : '管理自动执行的商品数据采集计划，随时查看最近一次运行状态。' }}</p>
    </section>

    <div v-if="activePanel === 'instant'" class="backend-sections">
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
            <label class="checkbox-label"><input v-model="form.no_overview" type="checkbox" /><span>不打印首页概览</span></label>
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
          <div class="output-heading">
            <span>执行输出</span>
            <div class="output-heading-actions">
              <label class="checkbox-label"><input v-model="autoScroll" type="checkbox" /><span>自动滚动</span></label>
            </div>
          </div>
          <pre ref="taskOutputElement" class="task-output">{{ task.output || '任务已启动，等待爬虫输出…' }}</pre>
        </template>
      </section>
    </div>

    <section v-else class="schedule-workspace" aria-label="定时任务管理">
      <section class="schedule-list-card" aria-labelledby="schedule-list-title">
        <div class="section-heading schedule-list-heading">
          <div>
            <p class="section-kicker">SCHEDULED OPERATIONS</p>
            <h2 id="schedule-list-title">定时任务</h2>
          </div>
          <button class="primary-button compact-button" type="button" @click="openCreateSchedule">
            <Plus :size="16" :stroke-width="2" aria-hidden="true" />
            <span>创建任务</span>
          </button>
        </div>

        <p v-if="scheduleError" class="error-message" role="alert">{{ scheduleError }}</p>
        <p v-if="scheduleNotice" class="notice-message" role="status"><Check :size="15" :stroke-width="2" aria-hidden="true" />{{ scheduleNotice }}</p>
        <div v-if="schedulesLoading && !schedules.length" class="schedule-empty">
          <LoaderCircle class="spin-icon" :size="24" :stroke-width="1.8" aria-hidden="true" />
          <strong>正在加载定时任务</strong>
          <span>正在同步任务配置与最近运行状态。</span>
        </div>
        <div v-else-if="!schedules.length" class="schedule-empty">
          <span class="empty-mark"><CalendarClock :size="20" :stroke-width="1.8" aria-hidden="true" /></span>
          <strong>还没有定时任务</strong>
          <span>创建一个任务，让商品数据按固定间隔自动更新。</span>
          <button class="secondary-button empty-action" type="button" @click="openCreateSchedule">创建第一个任务</button>
        </div>
        <div v-else class="schedule-table-wrap">
          <table class="schedule-table">
            <thead>
              <tr><th>任务</th><th>状态</th><th>执行间隔</th><th>最近状态</th><th>下次执行</th><th><span class="sr-only">操作</span></th></tr>
            </thead>
            <tbody>
              <tr v-for="schedule in schedules" :key="schedule.id" :class="{ selected: selectedScheduleId === schedule.id }" tabindex="0" @click="selectSchedule(schedule)" @keydown.enter="selectSchedule(schedule)">
                <td>
                  <div class="schedule-name-cell">
                    <strong :title="schedule.name || `任务 ${schedule.id}`">{{ schedule.name || `任务 ${schedule.id}` }}</strong>
                    <span :title="`#${schedule.id} · ${schedule.crawl_params?.category || '全部分类'}`">#{{ schedule.id }} · {{ schedule.crawl_params?.category || '全部分类' }}</span>
                  </div>
                </td>
                <td><span class="schedule-status" :class="schedule.enabled ? 'enabled' : 'disabled'"><span class="status-dot" :class="schedule.enabled ? 'enabled' : 'disabled'"></span>{{ schedule.enabled ? '启用' : '停用' }}</span></td>
                <td class="schedule-interval"><Clock3 :size="15" :stroke-width="1.8" aria-hidden="true" />{{ formatInterval(schedule.interval_seconds) }}</td>
                <td><span class="schedule-status" :class="scheduleStatusClass(schedule.last_status)"><span class="status-dot" :class="scheduleStatusClass(schedule.last_status)"></span>{{ scheduleStatusText(schedule.last_status) }}</span></td>
                <td class="schedule-next-run">{{ formatScheduleTime(schedule.next_run_at) }}</td>
                <td>
                  <div class="schedule-actions" @click.stop>
                    <button class="icon-action" type="button" :disabled="isScheduleTriggerDisabled(schedule)" aria-label="立即触发" :title="schedule.enabled ? '立即触发' : '任务已停用，无法触发'" @click="triggerSchedule(schedule)"><Play :size="15" :stroke-width="2" aria-hidden="true" /></button>
                    <button class="icon-action" type="button" :aria-label="schedule.enabled ? '停用任务' : '启用任务'" :title="schedule.enabled ? '停用任务' : '启用任务'" @click="toggleSchedule(schedule)">
                      <PowerOff v-if="schedule.enabled" :size="15" :stroke-width="2" aria-hidden="true" />
                      <Power v-else :size="15" :stroke-width="2" aria-hidden="true" />
                    </button>
                    <button class="icon-action" type="button" aria-label="编辑任务" title="编辑任务" @click="openEditSchedule(schedule)"><Edit3 :size="15" :stroke-width="1.8" aria-hidden="true" /></button>
                    <button class="icon-action danger-action" type="button" aria-label="删除任务" title="删除任务" @click="removeSchedule(schedule)"><Trash2 :size="15" :stroke-width="1.8" aria-hidden="true" /></button>
                  </div>
                </td>
              </tr>
            </tbody>
          </table>
        </div>
      </section>

      <section class="schedule-monitor-card" aria-labelledby="schedule-monitor-title">
        <div class="section-heading">
          <div>
            <p class="section-kicker">LIVE MONITOR</p>
            <h2 id="schedule-monitor-title">运行状态</h2>
          </div>
          <button class="refresh-button" type="button" aria-label="刷新定时任务" title="刷新" :disabled="schedulesLoading" @click="loadSchedules()"><RefreshCw :class="{ 'spin-icon': schedulesLoading }" :size="17" :stroke-width="1.8" aria-hidden="true" /></button>
        </div>

        <div v-if="!monitoredSchedule" class="schedule-empty monitor-empty">
          <span class="empty-mark"><Clock3 :size="20" :stroke-width="1.8" aria-hidden="true" /></span>
          <strong>选择一个定时任务</strong>
          <span>这里会展示任务配置和最近一次爬取的实时状态。</span>
        </div>
        <template v-else>
          <div class="monitor-title-row">
            <div>
              <span class="monitor-eyebrow">{{ monitoredSchedule.last_status === 'running' ? '当前运行的定时任务' : '已选定时任务' }}</span>
              <h3>{{ monitoredSchedule.name || `任务 ${monitoredSchedule.id}` }}</h3>
            </div>
            <span class="schedule-status large-status" :class="scheduleStatusTone"><span class="status-dot" :class="scheduleStatusTone"></span>{{ scheduleStatusLabel }}</span>
          </div>
          <div class="monitor-facts">
            <div><span>执行间隔</span><strong>{{ formatInterval(monitoredSchedule.interval_seconds) }}</strong></div>
            <div><span>下次执行</span><strong>{{ monitoredSchedule.enabled ? formatScheduleTime(monitoredSchedule.next_run_at) : '已停用' }}</strong></div>
            <div><span>最近开始</span><strong>{{ formatScheduleTime(monitoredSchedule.last_run_at) }}</strong></div>
            <div><span>最近完成</span><strong>{{ formatScheduleTime(monitoredSchedule.last_finished_at) }}</strong></div>
          </div>
          <div class="monitor-params">
            <span>页数 {{ monitoredSchedule.crawl_params?.pages === 0 ? '全量' : monitoredSchedule.crawl_params?.pages }}</span>
            <span>分类 {{ monitoredSchedule.crawl_params?.category || '全部' }}</span>
            <span>IP 分区 {{ monitoredSchedule.crawl_params?.ip || '不限' }}</span>
            <span>排序 {{ sortOptions.find((option) => option.value === monitoredSchedule.crawl_params?.sort)?.label || monitoredSchedule.crawl_params?.sort }}</span>
            <span>{{ monitoredSchedule.crawl_params?.detail ? '含商品详情' : '不含商品详情' }}</span>
            <span>{{ monitoredSchedule.crawl_params?.no_overview ? '不打印首页概览' : '打印首页概览' }}</span>
          </div>
          <p v-if="monitoredSchedule.last_error" class="error-message monitor-error" role="alert">{{ monitoredSchedule.last_error }}</p>
          <div v-if="scheduleTask" class="schedule-task-panel">
            <div class="output-heading">
              <span>执行输出</span>
              <div class="output-heading-actions">
                <label class="checkbox-label"><input v-model="scheduleAutoScroll" type="checkbox" /><span>自动滚动</span></label>
              </div>
            </div>
            <div class="task-facts">
              <div><span>任务 ID</span><strong class="compact-task-id" :title="scheduleTask.task_id || monitoredSchedule.last_task_id">{{ scheduleTask.task_id || monitoredSchedule.last_task_id }}</strong></div>
              <div><span>返回码</span><strong>{{ scheduleTask.return_code ?? '—' }}</strong></div>
            </div>
            <pre class="task-output schedule-output">{{ scheduleTask.output || '任务已启动，等待爬虫输出…' }}</pre>
          </div>
          <div v-else class="monitor-last-run"><span>最近任务 ID</span><strong>{{ monitoredSchedule.last_task_id || '尚未触发' }}</strong></div>
        </template>
      </section>
    </section>

    <AppFooter />
    <Teleport to="body">
      <div v-if="scheduleModalOpen" class="modal-backdrop" role="presentation">
        <section class="schedule-modal" role="dialog" aria-modal="true" aria-labelledby="schedule-modal-title">
          <div class="modal-heading">
            <div><p class="section-kicker">SCHEDULE CONFIGURATION</p><h2 id="schedule-modal-title">{{ scheduleFormTitle }}</h2></div>
            <button class="modal-close" type="button" aria-label="关闭弹窗" title="关闭" @click="closeScheduleModal"><X :size="20" :stroke-width="1.8" aria-hidden="true" /></button>
          </div>
          <p v-if="scheduleModalError" class="error-message" role="alert">{{ scheduleModalError }}</p>
          <form class="schedule-form" @submit.prevent="submitSchedule">
            <label class="wide-field"><span>任务名称</span><input v-model="scheduleForm.name" type="text" maxlength="100" placeholder="例如：每日商品巡检" /><small>便于在任务列表中识别</small></label>
            <label><span>执行间隔（秒）</span><input v-model.number="scheduleForm.interval_seconds" type="number" min="60" max="2592000" required /><small>最短 60 秒，最长 30 天</small></label>
            <label><span>抓取页数</span><input v-model.number="scheduleForm.pages" type="number" min="0" max="500" required /><small>0 表示全量抓取</small></label>
            <label><span>商品分类</span><input v-model="scheduleForm.category" type="text" placeholder="例如 898" /><small>留空表示全部分类</small></label>
            <label><span>IP 分区</span><input v-model="scheduleForm.ip" type="text" placeholder="可选" /><small>留空表示不限制</small></label>
            <BaseSelect v-model="scheduleForm.sort" label="排序方式" hint="对应爬虫排序参数" :options="sortOptions" />
            <div class="schedule-form-options wide-field"><label class="checkbox-label"><input v-model="scheduleForm.detail" type="checkbox" /><span>获取商品详情</span></label><label class="checkbox-label"><input v-model="scheduleForm.no_alert" type="checkbox" /><span>关闭价格异动检测</span></label><label class="checkbox-label"><input v-model="scheduleForm.no_overview" type="checkbox" /><span>不打印首页概览</span></label></div>
            <div class="modal-actions wide-field"><button class="secondary-button" type="button" :disabled="scheduleSubmitting" @click="closeScheduleModal">取消</button><button class="primary-button" type="submit" :disabled="scheduleSubmitting"><LoaderCircle v-if="scheduleSubmitting" class="spin-icon" :size="16" :stroke-width="2" aria-hidden="true" /><span>{{ scheduleSubmitting ? '保存中…' : '保存任务' }}</span></button></div>
          </form>
        </section>
      </div>
    </Teleport>
  </main>
</template>

<style scoped>
.backend-page { width: min(1280px, calc(100% - 64px)); margin: 0 auto; padding-bottom: 64px; }
.backend-nav { position: relative; display: flex; align-items: center; justify-content: center; height: 80px; border-bottom: 1px solid var(--color-border-soft); }
.brand { position: absolute; left: 0; display: flex; align-items: center; gap: 8px; color: var(--color-text-primary); font-size: var(--fs-16); font-weight: 600; text-decoration: none; }
.brand-mark { display: grid; width: 32px; height: 32px; place-items: center; border-radius: 50%; background: var(--color-accent); color: var(--color-on-accent); font-size: var(--fs-20); font-weight: 600; }
.brand-name { letter-spacing: -.2px; }
.backend-page-nav { display: flex; align-self: stretch; gap: 32px; }
.backend-page-tab { position: relative; display: flex; align-items: center; gap: 8px; color: var(--color-text-muted); font-size: var(--fs-14); font-weight: 500; text-decoration: none; }
.backend-page-tab::after { position: absolute; right: 0; bottom: 0; left: 0; height: 2px; background: transparent; content: ''; }
.backend-page-tab:hover, .backend-page-tab:focus-visible, .backend-page-tab.active { color: var(--color-text-primary); }
.backend-page-tab.active::after { background: var(--color-text-primary); }
.backend-page-tab-icon { display: grid; width: 24px; height: 24px; place-items: center; }
.backend-nav-actions { position: absolute; right: 0; display: flex; align-items: center; gap: 0; }
.back-link { margin-right: 16px; color: var(--color-text-muted); font-size: var(--fs-14); text-decoration: none; }
.back-link:hover, .back-link:focus-visible { color: var(--color-text-primary); text-decoration: underline; text-underline-offset: 4px; }
.theme-toggle { display: grid; width: 40px; height: 40px; padding: 0; place-items: center; border: 1px solid var(--color-border); border-radius: 50%; background: var(--color-surface); color: var(--color-text-primary); cursor: pointer; }
.theme-toggle:hover, .theme-toggle:focus-visible { background: var(--color-surface-strong); box-shadow: var(--shadow-card); }
.backend-intro { padding: 64px 0 32px; }
.section-kicker { margin: 0 0 8px; color: var(--color-text-muted); font-size: var(--fs-11); font-weight: 700; letter-spacing: 1.2px; line-height: 1.3; text-transform: uppercase; }
.backend-intro h1 { margin: 0; color: var(--color-text-primary); font-size: var(--fs-28); font-weight: 700; line-height: 1.43; }
.backend-intro > p:last-child { margin: 12px 0 0; color: var(--color-text-muted); font-size: var(--fs-14); line-height: 1.5; }
.backend-sections { display: grid; gap: 24px; }
.control-card, .status-card { padding: 24px; border: 1px solid var(--color-border-soft); border-radius: 14px; background: var(--color-surface); }
.section-heading { display: flex; align-items: flex-start; justify-content: space-between; gap: 16px; margin-bottom: 24px; }
.section-heading .section-kicker { margin-bottom: 4px; }
.section-heading h2 { margin: 0; color: var(--color-text-primary); font-size: var(--fs-22); font-weight: 500; letter-spacing: -.44px; line-height: 1.2; }
.section-index { color: var(--color-text-disabled); font-size: var(--fs-12); font-weight: 600; }
.crawl-form { display: grid; grid-template-columns: repeat(4, minmax(0, 1fr)); gap: 24px 16px; }
.crawl-form label:not(.checkbox-label) { display: flex; flex-direction: column; gap: 8px; }
.crawl-form label > span:first-child { color: var(--color-text-primary); font-size: var(--fs-13); font-weight: 600; }
.crawl-form input[type="number"], .crawl-form input[type="text"], .crawl-form select { width: 100%; height: 48px; padding: 0 11px; border: 2px solid transparent; border-radius: 8px; outline: 0; background: var(--color-surface); color: var(--color-text-primary); font-size: var(--fs-14); box-shadow: inset 0 0 0 1px var(--color-border); }
.crawl-form input::placeholder { color: var(--color-text-disabled); }
/* The 2px border is always present and transparent, so focus only recolors it and the value,
   the placeholder and the caret never shift by a pixel (same rule as the search pill). */
.crawl-form input[type="number"]:focus, .crawl-form input[type="text"]:focus, .crawl-form select:focus { border-color: var(--color-focus); box-shadow: none; }
.crawl-form small { min-height: 16px; color: var(--color-text-disabled); font-size: var(--fs-12); line-height: 1.3; }
.form-options { display: flex; grid-column: 1 / -1; flex-wrap: wrap; gap: 24px; padding-top: 4px; border-top: 1px solid var(--color-border-soft); }
.checkbox-label { display: inline-flex; flex-direction: row !important; align-items: center; gap: 8px !important; padding-top: 16px; color: var(--color-text-secondary); font-size: var(--fs-13); white-space: nowrap; cursor: pointer; }
.checkbox-label input { width: 16px; height: 16px; accent-color: var(--color-accent); }
.form-actions { display: flex; grid-column: 1 / -1; align-items: center; justify-content: space-between; gap: 20px; padding-top: 8px; }
.form-actions p { margin: 0; color: var(--color-text-muted); font-size: var(--fs-13); }
.primary-button { display: inline-flex; min-width: 128px; height: 48px; align-items: center; justify-content: center; gap: 8px; padding: 0 20px; border: 0; border-radius: 8px; background: var(--color-accent); color: var(--color-on-accent); font-size: var(--fs-14); font-weight: 500; cursor: pointer; }
.primary-button:hover, .primary-button:focus-visible { background: var(--color-accent-hover); }
.primary-button:disabled { background: var(--color-accent-disabled); color: var(--color-on-accent-disabled); cursor: not-allowed; }
.secondary-button { display: inline-flex; min-width: 96px; height: 48px; align-items: center; justify-content: center; gap: 8px; padding: 0 20px; border: 1px solid var(--color-text-primary); border-radius: 8px; background: var(--color-surface); color: var(--color-text-primary); font-size: var(--fs-14); font-weight: 500; cursor: pointer; }
.secondary-button:hover, .secondary-button:focus-visible { background: var(--color-surface-strong); }
.secondary-button:disabled { border-color: var(--color-border); color: var(--color-text-disabled); cursor: not-allowed; }
.error-message { margin: 0 0 24px; padding: 12px 16px; border-radius: 8px; background: var(--color-error-surface); color: var(--color-error); font-size: var(--fs-13); }
.notice-message { display: flex; align-items: center; gap: 8px; margin: 0 0 24px; padding: 12px 16px; border-radius: 8px; background: var(--color-success-surface); color: var(--color-success); font-size: var(--fs-13); }
.status-empty { display: flex; min-height: 180px; flex-direction: column; align-items: center; justify-content: center; gap: 8px; color: var(--color-text-muted); text-align: center; }
.empty-mark { display: grid; width: 42px; height: 42px; margin-bottom: 4px; place-items: center; border-radius: 50%; background: var(--color-surface-strong); color: var(--color-text-disabled); font-size: var(--fs-22); }
.status-empty strong { color: var(--color-text-primary); font-size: var(--fs-16); font-weight: 600; }
.status-empty span:last-child { font-size: var(--fs-13); }
.status-summary { display: flex; align-items: center; justify-content: space-between; gap: 16px; padding: 16px; border-radius: 8px; background: var(--color-surface-soft); }
.status-main { display: flex; min-width: 0; align-items: center; gap: 8px; }
.status-dot { width: 8px; height: 8px; flex: 0 0 auto; border-radius: 50%; background: var(--color-text-disabled); }
.status-dot.running { background: var(--color-accent); box-shadow: 0 0 0 4px color-mix(in srgb, var(--color-accent) 16%, transparent); }
.status-dot.success { background: var(--color-success); }
.status-dot.failed { background: var(--color-error); }
.status-pill { color: var(--color-text-primary); font-size: var(--fs-14); font-weight: 600; }
.status-pill.success { color: var(--color-success); }
.status-pill.failed { color: var(--color-error); }
.task-id { overflow: hidden; color: var(--color-text-disabled); font-family: ui-monospace, SFMono-Regular, Consolas, monospace; font-size: var(--fs-11); text-overflow: ellipsis; white-space: nowrap; }
.polling-label { flex: 0 0 auto; color: var(--color-text-muted); font-size: var(--fs-12); }
.task-facts { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 12px; margin-top: 16px; }
.task-facts div { display: flex; align-items: baseline; justify-content: space-between; gap: 12px; padding-bottom: 12px; border-bottom: 1px solid var(--color-border-soft); color: var(--color-text-muted); font-size: var(--fs-13); }
/* Labels such as "任务 ID" contain a space and would otherwise break across two lines
   once the value column takes its width; the value shrinks with an ellipsis instead. */
.task-facts div > span { flex: 0 0 auto; white-space: nowrap; }
.task-facts strong { min-width: 0; color: var(--color-text-primary); font-weight: 500; }
.output-heading { display: flex; flex-wrap: wrap; align-items: center; justify-content: space-between; gap: 8px 16px; margin-top: 24px; color: var(--color-text-primary); font-size: var(--fs-13); font-weight: 600; }
.output-heading-actions { display: flex; align-items: center; gap: 16px; }
/* The terminal's auto-scroll toggle is a secondary control, so it drops the checkbox
   row's top padding and the heading's weight/colour. */
.output-heading .checkbox-label { padding-top: 0; color: var(--color-text-muted); font-size: var(--fs-12); font-weight: 500; }
.task-output { min-height: 180px; max-height: 360px; margin: 12px 0 0; padding: 16px; overflow: auto; border-radius: 8px; background: var(--color-surface-soft); color: var(--color-text-secondary); font-family: ui-monospace, SFMono-Regular, Consolas, monospace; font-size: var(--fs-12); line-height: 1.5; white-space: pre-wrap; word-break: break-word; }
.compact-button { min-width: 120px; height: 44px; padding: 0 16px; }
.schedule-workspace { display: grid; grid-template-columns: minmax(0, 1.5fr) minmax(340px, .9fr); gap: 24px; align-items: start; }
.schedule-list-card, .schedule-monitor-card { min-width: 0; padding: 24px; border: 1px solid var(--color-border-soft); border-radius: 14px; background: var(--color-surface); }
.schedule-list-heading { align-items: center; margin-bottom: 16px; }
.schedule-table-wrap { margin: 0 -24px -24px; overflow-x: auto; }
.schedule-table { width: 100%; border-collapse: collapse; color: var(--color-text-secondary); font-size: var(--fs-13); }
.schedule-table th { padding: 0 16px 12px; border-bottom: 1px solid var(--color-border-soft); color: var(--color-text-disabled); font-size: var(--fs-11); font-weight: 600; text-align: left; white-space: nowrap; }
.schedule-table th:first-child, .schedule-table td:first-child { padding-left: 24px; }
.schedule-table th:last-child, .schedule-table td:last-child { padding-right: 24px; }
.schedule-table td { height: 76px; padding: 12px 16px; border-bottom: 1px solid var(--color-border-soft); vertical-align: middle; }
.schedule-table tbody tr { outline: 0; cursor: pointer; transition: background-color var(--duration-fast) var(--ease-standard); }
.schedule-table tbody tr:hover, .schedule-table tbody tr:focus-visible, .schedule-table tbody tr.selected { background: var(--color-surface-soft); }
.schedule-table tbody tr:last-child td { border-bottom: 0; }
/* The name cell is the only column with room to give — the other five are nowrap, so the old
   140px floor held the table slightly wider than the card and popped the x-scrollbar. Capping it
   pins the column at a predictable width instead, the same truncating-cell pattern as
   .compact-task-id, so both lines carry a title to keep their full text reachable. */
.schedule-name-cell { display: flex; max-width: 112px; flex-direction: column; gap: 4px; }
.schedule-name-cell strong { overflow: hidden; color: var(--color-text-primary); font-size: var(--fs-14); font-weight: 600; text-overflow: ellipsis; white-space: nowrap; }
.schedule-name-cell span, .schedule-next-run { color: var(--color-text-muted); font-size: var(--fs-12); white-space: nowrap; }
.schedule-name-cell span { overflow: hidden; text-overflow: ellipsis; }
.schedule-interval { display: inline-flex; align-items: center; gap: 4px; white-space: nowrap; }
.schedule-status { display: inline-flex; align-items: center; gap: 8px; color: var(--color-text-muted); font-size: var(--fs-12); white-space: nowrap; }
.schedule-status.running, .schedule-status.success { color: var(--color-success); }
.schedule-status.failed, .schedule-status.error { color: var(--color-error); }
.schedule-status.skipped { color: var(--color-text-muted); }
/* Enabled flag column: green when the schedule is armed, muted once it is switched off. */
.schedule-status.enabled { color: var(--color-success); }
.schedule-status.disabled { color: var(--color-text-disabled); }
.status-dot.pending { background: var(--color-text-disabled); }
.status-dot.skipped { background: var(--color-text-disabled); }
.status-dot.enabled { background: var(--color-success); }
.status-dot.disabled { background: var(--color-text-disabled); }
.status-dot.error { background: var(--color-error); }
.schedule-actions { display: flex; align-items: center; justify-content: flex-end; gap: 4px; }
.icon-action, .refresh-button, .modal-close { display: grid; width: 36px; height: 36px; padding: 0; place-items: center; border: 1px solid transparent; border-radius: 50%; background: transparent; color: var(--color-text-muted); cursor: pointer; }
.icon-action:hover, .icon-action:focus-visible, .refresh-button:hover, .refresh-button:focus-visible, .modal-close:hover, .modal-close:focus-visible { border-color: var(--color-border); background: var(--color-surface-strong); color: var(--color-text-primary); }
.icon-action:disabled, .refresh-button:disabled { color: var(--color-text-disabled); cursor: not-allowed; }
.icon-action.danger-action:hover, .icon-action.danger-action:focus-visible { border-color: var(--color-error); color: var(--color-error); }
.schedule-empty { display: flex; min-height: 300px; flex-direction: column; align-items: center; justify-content: center; gap: 8px; color: var(--color-text-muted); text-align: center; }
.schedule-empty strong { color: var(--color-text-primary); font-size: var(--fs-16); font-weight: 600; }
.schedule-empty > span:last-of-type { max-width: 260px; font-size: var(--fs-13); line-height: 1.5; }
.empty-action { height: 42px; margin-top: 16px; }
.monitor-empty { min-height: 300px; }
.monitor-title-row { display: flex; align-items: flex-start; justify-content: space-between; gap: 16px; padding-bottom: 16px; border-bottom: 1px solid var(--color-border-soft); }
.monitor-eyebrow { color: var(--color-text-muted); font-size: var(--fs-11); font-weight: 600; letter-spacing: .5px; }
.monitor-title-row h3 { margin: 4px 0 0; color: var(--color-text-primary); font-size: var(--fs-20); font-weight: 600; line-height: 1.2; }
.large-status { margin-top: 4px; font-size: var(--fs-13); font-weight: 600; }
.monitor-facts { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 0 16px; }
.monitor-facts div { display: flex; min-width: 0; flex-direction: column; gap: 4px; padding: 16px 0; border-bottom: 1px solid var(--color-border-soft); }
.monitor-facts span, .monitor-last-run span { color: var(--color-text-muted); font-size: var(--fs-12); }
.monitor-facts strong { overflow: hidden; color: var(--color-text-primary); font-size: var(--fs-13); font-weight: 500; text-overflow: ellipsis; white-space: nowrap; }
.monitor-params { display: flex; flex-wrap: wrap; gap: 8px; margin-top: 20px; }
.monitor-params span { padding: 6px 8px; border-radius: 9999px; background: var(--color-surface-soft); color: var(--color-text-secondary); font-size: var(--fs-11); }
.monitor-error { margin-top: 20px; margin-bottom: 0; }
.schedule-task-panel { margin-top: 24px; }
/* 返回码 is at most a few characters, so the task ID takes the wider column. */
.schedule-task-panel .task-facts { grid-template-columns: minmax(0, 1.5fr) minmax(0, .7fr); }
.compact-task-id { max-width: 152px; overflow: hidden; font-family: ui-monospace, SFMono-Regular, Consolas, monospace; text-overflow: ellipsis; white-space: nowrap; }
.schedule-output { min-height: 150px; max-height: 250px; }
.monitor-last-run { display: flex; align-items: center; justify-content: space-between; gap: 12px; margin-top: 24px; padding-top: 16px; border-top: 1px solid var(--color-border-soft); }
.monitor-last-run span { flex: 0 0 auto; white-space: nowrap; }
.monitor-last-run strong { min-width: 0; max-width: 192px; overflow: hidden; color: var(--color-text-disabled); font-family: ui-monospace, SFMono-Regular, Consolas, monospace; font-size: var(--fs-11); text-overflow: ellipsis; white-space: nowrap; }
.sr-only { position: absolute; width: 1px; height: 1px; padding: 0; overflow: hidden; clip: rect(0, 0, 0, 0); white-space: nowrap; border: 0; }
.spin-icon { animation: spin var(--duration-spin) linear infinite; }
@keyframes spin { to { transform: rotate(360deg); } }
.modal-backdrop { position: fixed; z-index: 20; inset: 0; display: grid; padding: 24px; place-items: center; background: var(--color-scrim); }
.schedule-modal { width: min(680px, 100%); max-height: min(760px, calc(100vh - 48px)); padding: 32px; overflow: auto; border: 1px solid var(--color-border-soft); border-radius: 14px; background: var(--color-surface); box-shadow: var(--shadow-drawer); }
.modal-heading { display: flex; align-items: flex-start; justify-content: space-between; gap: 20px; margin-bottom: 28px; }
.modal-heading h2 { margin: 0; color: var(--color-text-primary); font-size: var(--fs-22); font-weight: 500; letter-spacing: -.44px; line-height: 1.2; }
.modal-close { flex: 0 0 auto; }
.schedule-form { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 20px 16px; }
.schedule-form > label { display: flex; min-width: 0; flex-direction: column; gap: 8px; }
.schedule-form label > span:first-child { color: var(--color-text-primary); font-size: var(--fs-13); font-weight: 600; }
.schedule-form input:not([type="checkbox"]), .schedule-form select { width: 100%; height: 48px; padding: 0 11px; border: 2px solid transparent; border-radius: 8px; outline: 0; background: var(--color-surface); color: var(--color-text-primary); font-size: var(--fs-14); box-shadow: inset 0 0 0 1px var(--color-border); }
.schedule-form input::placeholder { color: var(--color-text-disabled); }
.schedule-form input:not([type="checkbox"]):focus, .schedule-form select:focus { border-color: var(--color-focus); box-shadow: none; }
.schedule-form small { min-height: 16px; color: var(--color-text-disabled); font-size: var(--fs-12); line-height: 1.3; }
.wide-field { grid-column: 1 / -1; }
.schedule-form-options { display: flex; flex-wrap: wrap; gap: 24px; padding-top: 4px; border-top: 1px solid var(--color-border-soft); }
.schedule-form-options .checkbox-label { padding-top: 16px; }
.modal-actions { display: flex; justify-content: flex-end; gap: 12px; padding-top: 8px; }
@media (max-width: 1128px) {
  .backend-page { width: min(100% - 48px, 960px); }
}
@media (max-width: 744px) {
  .backend-page { width: min(100% - 32px, 560px); }
  .backend-nav { height: 64px; }
  .brand-name { display: none; }
  .backend-page-nav { position: static; gap: 12px; transform: none; }
  .backend-page-tab { font-size: var(--fs-13); }
  .backend-nav-actions { gap: 0; }
  .backend-intro { padding: 48px 0 32px; }
  .control-card, .status-card { padding: 24px; }
  .crawl-form { grid-template-columns: repeat(2, minmax(0, 1fr)); }
  .form-actions { align-items: stretch; flex-direction: column; }
  .primary-button { width: 100%; }
  .status-summary { align-items: flex-start; flex-direction: column; }
  .polling-label { padding-left: 18px; }
  .schedule-workspace { display: flex; flex-direction: column; }
  .schedule-list-card, .schedule-monitor-card { width: 100%; padding: 24px; }
  .schedule-table-wrap { margin: 0 -24px -24px; }
  .schedule-table th:first-child, .schedule-table td:first-child { padding-left: 24px; }
  .schedule-table th:last-child, .schedule-table td:last-child { padding-right: 24px; }
  .schedule-table th:nth-child(3), .schedule-table td:nth-child(3) { display: none; }
  .schedule-next-run { display: none; }
  .schedule-table th:nth-child(5), .schedule-table td:nth-child(5) { display: none; }
  .schedule-actions { gap: 0; }
  .icon-action { width: 34px; height: 34px; }
  .modal-backdrop { padding: 12px; }
  .schedule-modal { max-height: calc(100vh - 24px); padding: 24px 16px; }
}
@media (max-width: 420px) {
  .backend-page { width: calc(100% - 24px); }
  .crawl-form { display: block; }
  .crawl-form > label { margin-bottom: 18px; }
  .form-options { display: grid; gap: 0; }
  .form-actions { margin-top: 20px; }
  .task-facts { display: block; }
  .task-facts div + div { margin-top: 12px; }
  .backend-page-nav { gap: 8px; }
  .backend-page-tab { gap: 4px; font-size: var(--fs-12); }
  .backend-page-tab svg { display: none; }
  .schedule-list-heading { align-items: flex-start; }
  .compact-button { min-width: 104px; padding: 0 12px; }
  .schedule-table th:nth-child(4), .schedule-table td:nth-child(4) { display: none; }
  .schedule-table td { height: 68px; }
  .schedule-actions { justify-content: flex-start; }
  .schedule-form { display: block; }
  .schedule-form > label { margin-bottom: 18px; }
  .schedule-form-options { display: grid; gap: 0; }
  .modal-actions { margin-top: 20px; }
  .modal-actions .secondary-button, .modal-actions .primary-button { flex: 1; }
}
</style>
