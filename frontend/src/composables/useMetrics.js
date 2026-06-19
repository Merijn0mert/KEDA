import { ref, onMounted, onUnmounted } from 'vue'

const API = ''  // via Vite proxy

export function useMetrics(intervalMs = 1000) {
  const current = ref({ queue_length: 0, consumers: 0, cpu_percent: 0, memory_mb: 0 })
  const history = ref([])
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
      // silently keep previous history
    }
  }

  onMounted(() => {
    fetchCurrent()
    fetchHistory()
    timer = setInterval(() => {
      fetchCurrent()
      fetchHistory()
    }, intervalMs)
  })

  onUnmounted(() => clearInterval(timer))

  return { current, history, error }
}
