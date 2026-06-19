<template>
  <div class="card">
    <h2>Queue &amp; Workers – live</h2>
    <Line :data="chartData" :options="chartOptions" />
  </div>
</template>

<script setup>
import { computed } from 'vue'
import { Line } from 'vue-chartjs'
import {
  Chart as ChartJS, CategoryScale, LinearScale,
  PointElement, LineElement, Title, Tooltip, Legend, Filler
} from 'chart.js'

ChartJS.register(CategoryScale, LinearScale, PointElement, LineElement, Title, Tooltip, Legend, Filler)

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
        label: 'Queue lengte',
        data: h.map(p => p.queue_length),
        borderColor: '#6366f1',
        backgroundColor: 'rgba(99,102,241,0.1)',
        fill: true,
        tension: 0.3,
        yAxisID: 'y',
      },
      {
        label: 'Actieve workers',
        data: h.map(p => p.consumers),
        borderColor: '#10b981',
        backgroundColor: 'rgba(16,185,129,0.1)',
        fill: true,
        tension: 0.3,
        yAxisID: 'y1',
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
    y:  { type: 'linear', position: 'left',  title: { display: true, text: 'Jobs in queue' }, min: 0 },
    y1: { type: 'linear', position: 'right', title: { display: true, text: 'Workers' }, min: 0, max: 10, grid: { drawOnChartArea: false } },
  }
}
</script>
