<template>
  <div class="card">
    <h2>CPU – live (millicores)</h2>
    <Line :data="chartData" :options="chartOptions" />
  </div>
</template>

<script setup>
import { computed } from 'vue'
import { Line } from 'vue-chartjs'
import {
  Chart as ChartJS, CategoryScale, LinearScale,
  PointElement, LineElement, Title, Tooltip, Legend
} from 'chart.js'

ChartJS.register(CategoryScale, LinearScale, PointElement, LineElement, Title, Tooltip, Legend)

const props = defineProps({ history: Array })

const chartData = computed(() => {
  const h = props.history || []
  const labels = h.map(p => {
    const d = new Date(p.timestamp * 1000)
    return `${String(d.getMinutes()).padStart(2,'0')}:${String(d.getSeconds()).padStart(2,'0')}`
  })
  return {
    labels,
    datasets: [
      {
        label: 'Platform totaal (mc)',
        data: h.map(p => p.platform_mc ?? 0),
        borderColor: '#f59e0b',
        backgroundColor: 'rgba(245,158,11,0.1)',
        tension: 0.3,
        yAxisID: 'y',
        borderWidth: 2,
      },
      {
        label: 'Workers (mc)',
        data: h.map(p => p.workers_mc ?? 0),
        borderColor: '#10b981',
        backgroundColor: 'rgba(16,185,129,0.08)',
        tension: 0.3,
        yAxisID: 'y',
        borderDash: [4, 3],
      },
      {
        label: 'Producer (mc)',
        data: h.map(p => p.producer_mc ?? 0),
        borderColor: '#6366f1',
        backgroundColor: 'rgba(99,102,241,0.08)',
        tension: 0.3,
        yAxisID: 'y',
        borderDash: [2, 4],
      },
    ]
  }
})

const chartOptions = {
  responsive: true,
  animation: false,
  interaction: { mode: 'index', intersect: false },
  plugins: { legend: { position: 'top' } },
  scales: {
    y: {
      type: 'linear',
      position: 'left',
      title: { display: true, text: 'Millicores' },
      min: 0,
    },
  }
}
</script>
