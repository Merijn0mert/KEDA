<template>
  <div class="status-grid">
    <div class="stat-card" :class="{ active: current.queue_length > 0 }">
      <div class="stat-value">{{ current.queue_length >= 0 ? current.queue_length : '–' }}</div>
      <div class="stat-label">Jobs in queue</div>
    </div>
    <div class="stat-card" :class="{ active: current.consumers > 0 }">
      <div class="stat-value">{{ current.consumers }}</div>
      <div class="stat-label">Actieve workers</div>
    </div>
    <div class="stat-card">
      <div class="stat-value">{{ current.cpu_percent?.toFixed(1) }}%</div>
      <div class="stat-label">CPU (producer)</div>
    </div>
    <div class="stat-card">
      <div class="stat-value">{{ current.memory_mb?.toFixed(1) }} MB</div>
      <div class="stat-label">Geheugen (producer)</div>
    </div>
  </div>
</template>

<script setup>
defineProps({ current: Object })
</script>
