<!--
  Copyright (c) 2024-2026 Magnus Persson
  SPDX-License-Identifier: GPL-3.0-only
  BrewGraph — https://github.com/mp-se/brewgraph
-->

<!--
  Chooses the logo shown in the public tap list header from the fixed set the display app
  serves, or no logo. The symbols are monochrome SVGs painted with a mask, as the display does,
  so they take the text colour here too. They are loaded from the display app, which the
  gateway serves under /public/.
-->
<template>
  <div class="tap-logo-picker">
    <div class="app-field-label" id="tap-list-logo-label">Tap list logo</div>
    <div class="tap-logo-picker__grid" role="radiogroup" aria-labelledby="tap-list-logo-label">
      <button
        v-for="option in options"
        :key="option.key ?? 'none'"
        type="button"
        role="radio"
        class="tap-logo-picker__tile"
        :class="{ 'tap-logo-picker__tile--selected': option.key === modelValue }"
        :aria-checked="option.key === modelValue"
        :aria-label="option.label"
        :title="option.label"
        :disabled="disabled"
        :data-logo="option.key ?? 'none'"
        @click="emit('update:modelValue', option.key)"
      >
        <span
          v-if="option.key"
          class="tap-logo-picker__symbol"
          aria-hidden="true"
          :style="{ '--logo-url': `url(${logoSrc(option.key)})` }"
        ></span>
        <span v-else class="tap-logo-picker__none">No logo</span>
      </button>
    </div>
    <div class="tap-logo-picker__preview" data-testid="logo-preview">
      <span class="app-field-label">Preview</span>
      <span
        v-if="modelValue"
        class="tap-logo-picker__symbol tap-logo-picker__symbol--large"
        role="img"
        :aria-label="`${modelValue} logo preview`"
        :style="{ '--logo-url': `url(${logoSrc(modelValue)})` }"
      ></span>
      <span v-else class="text-muted">No logo</span>
    </div>
  </div>
</template>

<script setup lang="ts">
const TAP_LIST_LOGOS = [
  'hop',
  'barley',
  'barrel',
  'kettle',
  'bottle',
  'glass',
  'tap',
  'yeast'
] as const

withDefaults(defineProps<{ modelValue: string | null; disabled?: boolean }>(), {
  disabled: false
})
const emit = defineEmits<{ 'update:modelValue': [value: string | null] }>()

const DISPLAY_BASE = '/public'
const logoSrc = (key: string): string => `${DISPLAY_BASE}/logos/${key}.svg`

const options = [
  ...TAP_LIST_LOGOS.map((key) => ({ key: key as string | null, label: key })),
  { key: null as string | null, label: 'No logo' }
]
</script>

<style scoped>
.tap-logo-picker__grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(72px, 1fr));
  gap: 0.5rem;
  max-width: 480px;
}
.tap-logo-picker__tile {
  display: flex;
  align-items: center;
  justify-content: center;
  height: 64px;
  padding: 0.25rem;
  border: 1px solid currentColor;
  border-radius: 6px;
  background: transparent;
  color: inherit;
  cursor: pointer;
  opacity: 0.7;
}
.tap-logo-picker__tile--selected {
  border-width: 3px;
  opacity: 1;
  font-weight: 600;
}
.tap-logo-picker__symbol {
  display: inline-block;
  width: 36px;
  height: 36px;
  background-color: currentColor;
  -webkit-mask: var(--logo-url) center/contain no-repeat;
  mask: var(--logo-url) center/contain no-repeat;
}
.tap-logo-picker__symbol--large {
  width: 48px;
  height: 48px;
}
.tap-logo-picker__none {
  font-size: 0.85rem;
}
.tap-logo-picker__preview {
  display: flex;
  align-items: center;
  gap: 1rem;
  margin-top: 0.75rem;
}
</style>
