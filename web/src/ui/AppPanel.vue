<template>
  <section class="app-panel" :class="tone ? `app-panel--${tone}` : undefined">
    <header v-if="title" class="app-panel__title">
      {{ title }}
    </header>
    <div class="app-panel__divider"></div>
    <div class="app-panel__body">
      <slot />
    </div>
  </section>
</template>

<script setup lang="ts">
defineProps<{ title?: string; tone?: 'primary' | 'success' | 'info' | 'danger' | 'secondary' }>()
</script>
