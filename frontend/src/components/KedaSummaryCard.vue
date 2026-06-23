<template>
  <div class="status-grid">

    <div class="stat-card" :class="{ active: summary.total_jobs > 0 }">
      <div class="stat-value">{{ summary.total_jobs }}</div>
      <div class="stat-label">Totaal jobs verwerkt</div>
    </div>

    <div class="stat-card" :class="{ active: summary.system_time }">
        <div class="stat-value">
            {{ formatTime(summary.system_time) }}
        </div>
        <div class="stat-label">Totale systeemtijd</div>
    </div>

    <div class="stat-card" :class="{ active: summary.consumers > 0 }">
      <div class="stat-value">{{ summary.consumers }}</div>
      <div class="stat-label">Actieve workers</div>
    </div>

    <div class="stat-card" :class="{ active: summary.peak_workers > 0 }">
      <div class="stat-value">{{ summary.peak_workers }}</div>
      <div class="stat-label">Totale workers op piek</div>
    </div>

  </div>
</template>

<script setup>
defineProps({
  summary: {
    type: Object,
    default: () => ({
      total_jobs: 0,
      system_time: null,
      consumers: 0,
      peak_workers: 0
    })
  }
})

function formatTime(systemTime) {
  if (!systemTime) return '0s'

  let seconds = 0

  if (systemTime.status === 'completed') {
    seconds = systemTime.total_time_seconds || 0
  } 
  else if (systemTime.status === 'running') {
    seconds = systemTime.elapsed_seconds || 0
  }

  const min = Math.floor(seconds / 60)
  const sec = Math.floor(seconds % 60)

  return min > 0 ? `${min}m ${sec}s` : `${sec}s`
}
</script>