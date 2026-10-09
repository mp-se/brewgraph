<!-- Copyright (c) 2024-2026 Magnus Persson SPDX-License-Identifier: GPL-3.0-only -->
<template>
  <div class="row q-col-gutter-md q-mt-md">
    <div class="col-md-4" v-for="(device, index) in chamberTemps" :key="`chamber-${index}`">
      <AppCard v-if="device.error === undefined" :header="'Chamber: ' + device.mdns" color="info" title="">
        <div class="text-center" v-if="device?.pid_fridge_temp_connected">
          Fridge temp: {{ device?.pid_fridge_temp }} °{{ device?.pid_temp_format }}
        </div>
        <div class="text-center" v-if="device?.pid_beer_temp_connected">
          Beer temp: {{ device?.pid_beer_temp }} °{{ device?.pid_temp_format }}
        </div>
        <div class="text-center" v-if="device?.pid_mode == 'b'">
          Mode: Beer target => {{ device?.pid_beer_target_temp }} °{{ device?.pid_temp_format }}
        </div>
        <div class="text-center" v-if="device?.pid_mode == 'f'">
          Mode: Fridge target => {{ device?.pid_fridge_target_temp }} °{{ device?.pid_temp_format }}
        </div>
        <div class="text-center" v-if="device?.pid_mode == 'o'">Mode: Off</div>
      </AppCard>
      <AppCard v-else :header="'Chamber: ' + device.mdns" color="danger" title="">
        <div class="text-center">{{ device.error }}</div>
      </AppCard>
    </div>

    <div class="col-md-4" v-for="(device, index) in kegmonTaps" :key="`kegmon-${index}`">
      <AppCard v-if="device.error === undefined" :header="'Kegmon: ' + device.mdns" color="info" title="">
        <div class="text-center">
          Tap1: {{ Number(device?.beer_volume1 / 100).toFixed(1) }} L, ({{ device?.glass1 }} glasses)
        </div>
        <div class="text-center">
          Tap2: {{ Number(device?.beer_volume2 / 100).toFixed(1) }} L, ({{ device?.glass2 }} glasses)
        </div>
        <div class="text-center">Temp: {{ device?.temperature }} °{{ device?.temp_format }}</div>
      </AppCard>
      <AppCard v-else :header="'Kegmon: ' + device.mdns" color="danger" title="">
        <div class="text-center">{{ device.error }}</div>
      </AppCard>
    </div>

    <div class="col-md-4" v-for="(device, index) in fermentationControlList" :key="`controller-${index}`">
      <AppCard :header="'Fermentation: ' + device.mdns + ', ' + device.description" color="info" title="">
        <div class="text-center">Controller has assigned profile</div>
      </AppCard>
    </div>

    <div class="col-md-4" v-if="schedulerStatus != null">
      <AppCard header="Scheduler" color="secondary" title="">
        <template v-if="schedulerStatus.length == 0">
          <div class="text-center">Scheduler disabled</div>
        </template>
        <template v-for="(task, index) in schedulerStatus" :key="index">
          <div class="text-center">
            {{ prettySchedulerName(task.name) }}: {{ prettySeconds(task.nextRunIn) }}
          </div>
        </template>
      </AppCard>
    </div>

    <div class="col-md-4">
      <AppCard header="Database Metrics" color="secondary" title="">
        <div class="text-center">{{ deviceCount }} devices in database</div>
        <div class="text-center">{{ batchCount }} batches in database</div>
        <div class="text-center">{{ vesselCount }} vessels in database</div>
        <div class="text-center">{{ tapCount }} taps in database</div>
        <div class="text-center">{{ gravityCount }} gravity points in database</div>
        <div class="text-center">{{ pourCount }} pour points in database</div>
        <div class="text-center">{{ pressureCount }} pressure points in database</div>
      </AppCard>
    </div>
  </div>
</template>

<script setup>
defineProps({
  chamberTemps: { type: Array, default: () => [] },
  kegmonTaps: { type: Array, default: () => [] },
  fermentationControlList: { type: Array, default: () => [] },
  schedulerStatus: { type: Array, default: null },
  deviceCount: { type: Number, required: true },
  batchCount: { type: Number, required: true },
  vesselCount: { type: Number, required: true },
  tapCount: { type: Number, required: true },
  gravityCount: { type: Number, required: true },
  pourCount: { type: Number, required: true },
  pressureCount: { type: Number, required: true }
})

function prettySchedulerName(name) {
  const names = {
    task_update_predictions: 'Fermentation ready prediction',
    task_check_database: 'Database maintenance',
    task_soft_delete_purge: 'Deleted data purge',
    task_chamber_step_reminder: 'Chamber temperature reminder',
    task_tap_line_reminder: 'Tap line cleaning reminder',
    task_drain_gravity_forward_queue: 'Forward gravity data',
    task_reclaim_stale_gravity_forwards: 'Retry gravity forwards',
    task_drain_pressure_forward_queue: 'Forward pressure data',
    task_reclaim_stale_pressure_forwards: 'Retry pressure forwards',
    task_drain_pour_forward_queue: 'Forward pour data',
    task_reclaim_stale_pour_forwards: 'Retry pour forwards',
    task_drain_temp_forward_queue: 'Forward temperature data',
    task_reclaim_stale_temp_forwards: 'Retry temperature forwards'
  }

  return names[name] ?? 'Unknown mapping'
}

function prettySeconds(seconds) {
  if (seconds < 60) return seconds + ' s'
  if (seconds < 3600) return Math.round(seconds / 60) + ' m'
  return Math.round(seconds / 3600) + ' h'
}
</script>
