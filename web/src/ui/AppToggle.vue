<template>
  <label class="app-toggle">
    <input
      type="checkbox"
      :checked="modelValue"
      :disabled="disabled"
      @change="updateValue"
    />
    <span class="app-toggle__track" aria-hidden="true"></span>
    <span>{{ label }}</span>
  </label>
</template>

<script setup lang="ts">
defineProps<{ modelValue: boolean; label: string; disabled?: boolean }>()
const emit = defineEmits<{ 'update:modelValue': [value: boolean] }>()

function updateValue(event: Event) {
  emit('update:modelValue', (event.target as HTMLInputElement).checked)
}
</script>
