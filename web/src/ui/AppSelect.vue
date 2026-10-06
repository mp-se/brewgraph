<template>
  <label class="app-select">
    <span v-if="label" class="app-field-label">{{ label }}</span>
    <select
      :value="modelValue"
      :disabled="disabled"
      class="app-native-input"
      @change="updateValue"
    >
      <option v-for="option in options" :key="optionValue(option)" :value="optionValue(option)">
        {{ optionLabel(option) }}
      </option>
    </select>
  </label>
</template>

<script setup lang="ts">
defineProps<{ modelValue: string; label?: string; options: unknown[]; disabled?: boolean }>()
const emit = defineEmits<{ 'update:modelValue': [value: string] }>()

function optionValue(option: unknown) {
  return typeof option === 'object' && option !== null ? String((option as { value?: unknown }).value ?? '') : String(option)
}

function optionLabel(option: unknown) {
  return typeof option === 'object' && option !== null ? String((option as { label?: unknown }).label ?? optionValue(option)) : String(option)
}

function updateValue(event: Event) {
  emit('update:modelValue', (event.target as HTMLSelectElement).value)
}
</script>
