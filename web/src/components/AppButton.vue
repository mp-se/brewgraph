<template>
  <q-btn no-caps :class="buttonClasses" v-bind="$attrs">
    <slot />
  </q-btn>
</template>

<script setup lang="ts">
import { computed } from 'vue'

type Variant = 'primary' | 'secondary' | 'positive' | 'negative' | 'warning' | 'info' |
  'outline-primary' | 'outline-secondary' | 'outline-negative' | 'outline-positive'

const props = defineProps<{ variant?: Variant; dense?: boolean }>()

const buttonClasses = computed(() => [
  'app-button',
  props.variant && `app-button--${props.variant}`,
  props.dense && 'app-button--dense'
])
</script>
