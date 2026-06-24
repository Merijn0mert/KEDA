<template>
  <div class="status-grid">
    <div class="stat-card" :class="{ active: current.queue_length > 0 }">
      <div class="stat-value">{{ current.queue_length >= 0 ? current.queue_length : '–' }}</div>
      <div class="stat-label">Jobs in queue</div>
    </div>
    <div class="stat-card" :class="{ active: current.active_jobs > 0 }">
      <div class="stat-value">{{ current.active_jobs }}</div>
      <div class="stat-label">Jobs in verwerking</div>
    </div>
    <div class="stat-card">
      <div class="stat-value">{{ current.platform_mc?.toFixed(0) ?? '0' }} <span style="font-size:14px;color:var(--text-muted)">mc</span></div>
      <div class="stat-label">Platform CPU (live)</div>
    </div>
    <div class="stat-card" :class="{ active: (summary?.total_cpu_millicore_seconds ?? 0) > 0 }">
      <div class="stat-value">{{ summary?.total_cpu_millicore_seconds?.toFixed(0) ?? '0' }} <span style="font-size:14px;color:var(--text-muted)">mc·s</span></div>
      <div class="stat-label">CPU verbruik (run)</div>
    </div>
  </div>
</template>

<script setup>
defineProps({
  current: Object,
  summary: Object,
})
</script>