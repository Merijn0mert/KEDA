import { ref, onMounted, onUnmounted } from 'vue'

const API = ''  // via Vite proxy

export function useMetrics(intervalMs = 1000) {
  const current = ref({
    queue_length: 0,
    consumers: 0,
    cpu_percent: 0,
    memory_mb: 0
  })

  const history = ref([])

  const summary = ref({
    total_jobs: 0,
    total_processing_time_ms: 0,
    consumers: 0,
    peak_workers: 0
  })

  const error = ref(null)
  let timer = null

  async function fetchCurrent() {
    try {
      const res = await fetch(`/api/metrics/current`)
      if (!res.ok) throw new Error(res.statusText)
      current.value = await res.json()
      error.value = null
    } catch (e) {
      error.value = e.message
    }
  }

  async function fetchHistory() {
    try {
      const res = await fetch(`/api/metrics/history`)
      if (!res.ok) throw new Error(res.statusText)
      history.value = await res.json()
    } catch (e) {
      error.value = e.message
    }
  }

  // ✅ ADDED
  async function fetchSummary() {
    try {
      const res = await fetch(`/api/metrics/summary`)
      if (!res.ok) throw new Error(res.statusText)
      summary.value = await res.json()
      console.log("🔥 RAW RESPONSE:", summary.value)
      console.log("⏱ system_time:", summary.value.system_time)

    } catch (e) {
      error.value = e.message
    }
  }

  onMounted(() => {
    fetchCurrent()
    fetchHistory()
    fetchSummary()

    timer = setInterval(() => {
      fetchCurrent()
      fetchHistory()
      fetchSummary()
    }, intervalMs)
  })

  onUnmounted(() => clearInterval(timer))

  return { current, history, summary, error }
}