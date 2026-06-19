import { ref, onMounted, onUnmounted } from 'vue'

export function useQueueStatus() {
  const queueLength = ref(0)
  const consumers = ref(0)
  const history = ref([])       // { time, length }
  const maxHistory = 60         // 60 datapunten = ~1 minuut bij interval 1s

  let interval = null

  async function fetchStatus() {
    try {
      const res = await fetch('/api/queue-status')
      const data = await res.json()
      queueLength.value = data.queue_length
      consumers.value = data.consumers

      const now = new Date().toLocaleTimeString('nl-NL', { hour: '2-digit', minute: '2-digit', second: '2-digit' })
      history.value.push({ time: now, length: data.queue_length, consumers: data.consumers })
      if (history.value.length > maxHistory) history.value.shift()
    } catch {
      // producer nog niet bereikbaar
    }
  }

  onMounted(() => {
    fetchStatus()
    interval = setInterval(fetchStatus, 1500)
  })

  onUnmounted(() => clearInterval(interval))

  return { queueLength, consumers, history }
}
