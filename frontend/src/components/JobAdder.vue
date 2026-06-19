<template>
  <div class="card">
    <h3>Jobs toevoegen</h3>
    <div class="input-row">
      <button @click="addJobs(1)" :disabled="loading">+ 1 job</button>
      <button @click="addJobs(10)" :disabled="loading">+ 10 jobs</button>
      <button @click="addJobs(50)" :disabled="loading">+ 50 jobs</button>
      <button @click="addJobs(100)" :disabled="loading">+ 100 jobs</button>
    </div>
    <div class="custom-row">
      <input v-model.number="customCount" type="number" min="1" max="10000" placeholder="Aangepast aantal" />
      <button @click="addJobs(customCount)" :disabled="loading || !customCount">Toevoegen</button>
    </div>
    <p v-if="lastResult" class="result" :class="lastResult.ok ? 'ok' : 'err'">
      {{ lastResult.message }}
    </p>
  </div>
</template>

<script setup>
import { ref } from 'vue'

const loading = ref(false)
const customCount = ref(null)
const lastResult = ref(null)

async function addJobs(count) {
  if (!count || count < 1) return
  loading.value = true
  lastResult.value = null
  try {
    const res = await fetch('/api/add-job', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ count })
    })
    const data = await res.json()
    if (res.ok) {
      lastResult.value = { ok: true, message: `✓ ${data.queued} job(s) toegevoegd in ${data.duration_ms}ms` }
    } else {
      lastResult.value = { ok: false, message: `✗ Fout: ${data.detail}` }
    }
  } catch (e) {
    lastResult.value = { ok: false, message: `✗ Kan producer niet bereiken` }
  } finally {
    loading.value = false
  }
}
</script>
