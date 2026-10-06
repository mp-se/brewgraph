<template>
  <section class="app-page-heading">
    <div>
      <h1>{{ title }}</h1>
    </div>
    <div v-if="$slots.default" class="app-page-heading__actions">
      <slot />
    </div>
  </section>
  <hr class="app-page-divider" />
</template>

<script setup lang="ts">
defineProps<{ title: string }>()
</script>
