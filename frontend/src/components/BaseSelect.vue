<script setup>
import { computed, nextTick, onBeforeUnmount, onMounted, ref } from 'vue'
import { ChevronDown } from 'lucide-vue-next'

defineOptions({ name: 'BaseSelect' })

const props = defineProps({
  modelValue: { type: String, required: true },
  options: { type: Array, required: true },
  label: { type: String, required: true },
  hint: { type: String, default: '' },
  disabled: { type: Boolean, default: false },
})

const emit = defineEmits(['update:modelValue'])
const rootElement = ref(null)
const triggerElement = ref(null)
const optionElements = ref([])
const isOpen = ref(false)
const highlightedIndex = ref(-1)
const instanceId = Math.random().toString(36).slice(2, 10)
const listId = `base-select-options-${instanceId}`
const labelId = `base-select-label-${instanceId}`

const selectedIndex = computed(() => props.options.findIndex((option) => option.value === props.modelValue))
const selectedOption = computed(() => props.options[selectedIndex.value] || null)

function setOptionElement(element, index) {
  if (element) optionElements.value[index] = element
}

function focusHighlightedOption() {
  nextTick(() => optionElements.value[highlightedIndex.value]?.focus())
}

function openMenu() {
  if (props.disabled) return
  isOpen.value = true
  highlightedIndex.value = selectedIndex.value >= 0 ? selectedIndex.value : 0
  focusHighlightedOption()
}

function closeMenu(restoreFocus = false) {
  isOpen.value = false
  optionElements.value = []
  if (restoreFocus) nextTick(() => triggerElement.value?.focus())
}

function toggleMenu() {
  if (isOpen.value) closeMenu()
  else openMenu()
}

function selectOption(value) {
  emit('update:modelValue', value)
  closeMenu(true)
}

function moveHighlight(step) {
  if (!props.options.length) return
  const currentIndex = highlightedIndex.value < 0 ? selectedIndex.value : highlightedIndex.value
  highlightedIndex.value = (currentIndex + step + props.options.length) % props.options.length
  focusHighlightedOption()
}

function handleTriggerKeydown(event) {
  if (event.key === 'Escape') {
    if (isOpen.value) {
      event.preventDefault()
      closeMenu(true)
    }
    return
  }
  if (event.key === 'ArrowDown' || event.key === 'ArrowUp') {
    event.preventDefault()
    if (!isOpen.value) openMenu()
    else moveHighlight(event.key === 'ArrowDown' ? 1 : -1)
  }
}

function handleOptionKeydown(event, index) {
  if (event.key === 'Escape') {
    event.preventDefault()
    closeMenu(true)
  } else if (event.key === 'ArrowDown' || event.key === 'ArrowUp') {
    event.preventDefault()
    highlightedIndex.value = index
    moveHighlight(event.key === 'ArrowDown' ? 1 : -1)
  } else if (event.key === 'Home' || event.key === 'End') {
    event.preventDefault()
    highlightedIndex.value = event.key === 'Home' ? 0 : props.options.length - 1
    focusHighlightedOption()
  }
}

function handleDocumentPointerdown(event) {
  if (isOpen.value && !rootElement.value?.contains(event.target)) closeMenu()
}

onMounted(() => document.addEventListener('pointerdown', handleDocumentPointerdown))
onBeforeUnmount(() => document.removeEventListener('pointerdown', handleDocumentPointerdown))
</script>

<template>
  <div ref="rootElement" class="select-field">
    <span :id="labelId" class="field-label">{{ label }}</span>
    <div class="select-control">
      <button
        ref="triggerElement"
        class="select-trigger"
        type="button"
        role="combobox"
        :aria-expanded="isOpen"
        :aria-controls="listId"
        :aria-labelledby="labelId"
        :disabled="disabled"
        @click="toggleMenu"
        @keydown="handleTriggerKeydown"
      >
        <span class="select-value">{{ selectedOption?.label || '请选择' }}</span>
        <ChevronDown :size="17" :stroke-width="1.8" :class="{ open: isOpen }" aria-hidden="true" />
      </button>
      <div v-if="isOpen" :id="listId" class="select-menu" role="listbox" :aria-labelledby="labelId">
        <button
          v-for="(option, index) in options"
          :key="option.value"
          :ref="(element) => setOptionElement(element, index)"
          class="select-option"
          :class="{ selected: option.value === modelValue, highlighted: index === highlightedIndex }"
          type="button"
          role="option"
          :aria-selected="option.value === modelValue"
          @click="selectOption(option.value)"
          @keydown="handleOptionKeydown($event, index)"
        >
          {{ option.label }}
        </button>
      </div>
    </div>
    <small v-if="hint">{{ hint }}</small>
  </div>
</template>

<style scoped>
.select-field { display: flex; min-width: 0; flex-direction: column; gap: 8px; }
.field-label { color: var(--color-text-primary); font-size: var(--fs-13); font-weight: 600; }
.select-control { position: relative; }
.select-trigger { display: flex; width: 100%; height: 48px; align-items: center; justify-content: space-between; gap: 12px; padding: 0 11px; border: 2px solid transparent; border-radius: 8px; outline: 0; background: var(--color-surface); color: var(--color-text-primary); font-size: var(--fs-14); text-align: left; cursor: pointer; box-shadow: inset 0 0 0 1px var(--color-border); }
.select-trigger:hover { box-shadow: inset 0 0 0 1px var(--color-border-strong); }
/* Always-present transparent border so focus recolors instead of reflowing the label. */
.select-trigger:focus-visible { border-color: var(--color-focus); box-shadow: none; }
/* IP 分区名可能很长，触发器保持单行，超出部分省略，控件宽度不随选中项变化。 */
.select-value { min-width: 0; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.select-trigger:disabled { color: var(--color-text-disabled); cursor: not-allowed; }
.select-trigger svg { flex: 0 0 auto; color: var(--color-text-muted); transition: transform var(--duration-base) var(--ease-standard); }
.select-trigger svg.open { transform: rotate(180deg); }
.select-menu { position: absolute; z-index: 20; top: calc(100% + 8px); right: 0; left: 0; display: grid; gap: 4px; max-height: 240px; padding: 4px; overflow-y: auto; border: 1px solid var(--color-border); border-radius: 8px; background: var(--color-surface); box-shadow: var(--shadow-card); }
.select-option { display: flex; min-height: 40px; align-items: center; padding: 0 12px; border: 0; border-radius: 8px; outline: 0; background: transparent; color: var(--color-text-primary); font-size: var(--fs-14); line-height: 1.43; text-align: left; cursor: pointer; }
.select-option:hover, .select-option.highlighted, .select-option:focus-visible { background: var(--color-surface-strong); }
.select-option.selected { color: var(--color-text-primary); font-weight: 500; }
/* Helper line below a control is {typography.caption-sm} in {colors.muted-soft} (DESIGN.md Forms). */
.select-field small { min-height: 16px; color: var(--color-text-disabled); font-size: var(--fs-13); line-height: 1.23; }
@media (prefers-reduced-motion: reduce) {
  .select-trigger svg { transition-duration: .01ms; }
}
</style>
