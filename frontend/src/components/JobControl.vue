<template>
  <div class="card">
    <h2>Jobs toevoegen</h2>
    <div class="controls">
      <input
        v-model.number="count"
        type="number"
        min="1"
        max="10000"
        placeholder="Aantal jobs"
      />
      <button @click="addJobs" :disabled="loading" class="btn-primary">
        {{ loading ? 'Bezig...' : `▶ Voeg ${count} job${count !== 1 ? 's' : ''} toe` }}
      </button>
    </div>
    <div class="quick-btns">
      <button @click="count = 1" class="btn-ghost">1</button>
      <button @click="count = 10" class="btn-ghost">10</button>
      <button @click="count = 50" class="btn-ghost">50</button>
      <button @click="count = 100" class="btn-ghost">100</button>
      <button @click="count = 500" class="btn-ghost">500</button>
    </div>
    <transition name="fade">
      <div v-if="lastResult" class="result" :class="lastResult.error ? 'error' : 'success'">
        {{ lastResult.error || `✓ ${lastResult.queued} jobs toegevoegd in ${lastResult.publish_time_ms}ms` }}
      </div>
    </transition>
  </div>
</template>

<script setup>
import { ref } from 'vue'

const count = ref(10)
const loading = ref(false)
const lastResult = ref(null)

async function addJobs() {
  loading.value = true
  lastResult.value = null
  try {
    const res = await fetch('/api/add-job', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ count: count.value }),
    })
    const data = await res.json()
    if (!res.ok) throw new Error(data.detail || 'Onbekende fout')
    lastResult.value = data
  } catch (e) {
    lastResult.value = { error: `Fout: ${e.message}` }
  } finally {
    loading.value = false
  }
}
</script>
