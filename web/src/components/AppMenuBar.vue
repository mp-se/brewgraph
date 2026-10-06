<!-- Copyright (c) 2024-2026 Magnus Persson SPDX-License-Identifier: GPL-3.0-only -->
<template>
  <QToolbar class="app-badge--primary text-white app-menu" aria-label="Main navigation">
    <QBtn flat round dense icon="menu" class="lt-md" aria-label="Toggle navigation" @click="expanded = !expanded" />
    <QToolbarTitle class="app-menu__brand">{{ brand }}</QToolbarTitle>
    <div class="gt-sm app-menu__links">
      <template v-for="item in items" :key="item.path">
        <QBtn v-if="!item.subs.length" flat no-caps class="app-menu__button" :disable="disabled" :class="{ 'text-weight-bold': isActive(item.path) }" :to="item.path" @click="closeMenus">
          <QIcon :name="item.icon" class="q-mr-xs" /><span>{{ item.label }}</span>
        </QBtn>
        <QBtnDropdown v-else flat no-caps class="app-menu__button" :disable="disabled" :class="{ 'text-weight-bold': isActive(item.path) }">
          <template #label><QIcon :name="item.icon" class="q-mr-xs" /><span>{{ item.label }}</span></template>
          <QList><QItem v-for="sub in item.subs" :key="sub.path" v-close-popup clickable :to="sub.external ? undefined : sub.path" :href="sub.external ? sub.path : undefined" :target="sub.external ? '_blank' : undefined" @click="closeMenus"><QItemSection>{{ sub.label }}</QItemSection></QItem></QList>
        </QBtnDropdown>
      </template>
    </div>
    <QSpace /><div class="app-menu__status"><span class="gt-xs">{{ mdns }}</span><QBadge v-if="needsSave" color="negative" label="Save needed" /><QSpinner v-if="disabled" color="white" size="1.5em" /><QToggle v-model="preferences.dark_mode" color="white" keep-color aria-label="Toggle colour theme" /></div>
  </QToolbar>
  <QSlideTransition><QList v-if="expanded" bordered class="lt-md app-mobile-menu"><template v-for="item in items" :key="item.path"><QItem v-if="!item.subs.length" clickable :disable="disabled" :to="item.path" @click="closeMenus"><QItemSection>{{ item.label }}</QItemSection></QItem><template v-else><QItemLabel header>{{ item.label }}</QItemLabel><QItem v-for="sub in item.subs" :key="sub.path" clickable :disable="disabled" :to="sub.external ? undefined : sub.path" :href="sub.external ? sub.path : undefined" :target="sub.external ? '_blank' : undefined" @click="closeMenus"><QItemSection>{{ sub.label }}</QItemSection></QItem></template></template></QList></QSlideTransition>
</template>
<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { useQuasar, QBadge, QBtn, QBtnDropdown, QIcon, QList, QItem, QItemLabel, QItemSection, QSlideTransition, QSpace, QSpinner, QToggle, QToolbar, QToolbarTitle } from 'quasar'
import { useRoute } from 'vue-router'
import { config, global, preferences } from '@/modules/pinia'
import { items } from '@/modules/router'
defineProps<{ disabled?: boolean; brand: string }>()
const route = useRoute(); const $q = useQuasar(); const expanded = ref(false)
const isActive = (path: string) => route.path.split('/')[1] === path.split('/')[1]
const needsSave = computed(() => global.configChanged || global.batchChanged || global.deviceChanged || global.tapChanged || global.vesselChanged)
const mdns = computed(() => (config as unknown as { mdns?: string }).mdns ?? '')
function closeMenus() { expanded.value = false }
watch(() => route.fullPath, closeMenus)
watch(() => preferences.dark_mode, value => { document.documentElement.setAttribute('data-theme', value ? 'dark' : 'light'); $q.dark.set(value) }, { immediate: true })
</script>
