<template>
  <div class="app">
    <header>
      <div class="header-inner">
        <div class="logo">
          <span class="logo-icon">⚡</span>
          <span>KEDA PoC Dashboard</span>
        </div>
        <div class="header-status">
          <span class="dot" :class="error ? 'dot-red' : 'dot-green'"></span>
          {{ error ? 'Geen verbinding met API' : 'Verbonden' }}
        </div>
      </div>
    </header>

    <main>
      <StatusCards :current="current" />
      <KedaSummaryCard :summary="summary" />
      
      <div class="two-col">
        <JobControl />
        <div class="card worker-status">
          <h2>Worker status</h2>
          <div v-if="current.consumers === 0" class="worker-idle">
            <span class="worker-icon">💤</span>
            <span>Geen actieve workers</span>
          </div>
          <div v-else class="worker-list">
            <div
              v-for="n in current.consumers"
              :key="n"
              class="worker-item"
            >
              <span class="worker-icon spinning">⚙️</span>
              <span>Worker {{ n }} — verwerkt job (~5s)</span>
            </div>
          </div>
          <div class="worker-hint">
            Schaal handmatig: <code>docker compose up --scale worker=N</code>
          </div>
        </div>
      </div>

      <QueueChart :history="history" />
      <CpuChart :history="history" />
    </main>
  </div>
</template>

<script setup>
import { useMetrics } from './composables/useMetrics.js'
import StatusCards from './components/StatusCards.vue'
import JobControl from './components/JobControl.vue'
import QueueChart from './components/QueueChart.vue'
import CpuChart from './components/CpuChart.vue'
import KedaSummaryCard from './components/KedaSummaryCard.vue'

const { current, history, error, summary } = useMetrics(1000)
</script>

<style>
*, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; }

:root {
  --bg: #0f172a;
  --surface: #1e293b;
  --border: #334155;
  --text: #f1f5f9;
  --text-muted: #94a3b8;
  --indigo: #6366f1;
  --green: #10b981;
  --amber: #f59e0b;
  --red: #ef4444;
}

body { background: var(--bg); color: var(--text); font-family: system-ui, sans-serif; font-size: 14px; }

.app { min-height: 100vh; }

header {
  background: var(--surface);
  border-bottom: 1px solid var(--border);
  padding: 0 24px;
  height: 56px;
  display: flex;
  align-items: center;
}

.header-inner { display: flex; align-items: center; justify-content: space-between; width: 100%; }

.logo { display: flex; align-items: center; gap: 10px; font-weight: 600; font-size: 16px; }
.logo-icon { font-size: 20px; }

.header-status { display: flex; align-items: center; gap: 8px; color: var(--text-muted); font-size: 13px; }
.dot { width: 8px; height: 8px; border-radius: 50%; }
.dot-green { background: var(--green); box-shadow: 0 0 6px var(--green); }
.dot-red   { background: var(--red);   box-shadow: 0 0 6px var(--red); }

main { max-width: 1200px; margin: 0 auto; padding: 24px; display: flex; flex-direction: column; gap: 20px; }

/* Status cards */
.status-grid { display: grid; grid-template-columns: repeat(4, 1fr); gap: 16px; }
@media (max-width: 700px) { .status-grid { grid-template-columns: repeat(2, 1fr); } }

.stat-card {
  background: var(--surface);
  border: 1px solid var(--border);
  border-radius: 10px;
  padding: 20px;
  text-align: center;
  transition: border-color 0.3s;
}
.stat-card.active { border-color: var(--indigo); }
.stat-value { font-size: 32px; font-weight: 700; color: var(--text); }
.stat-label { margin-top: 4px; color: var(--text-muted); font-size: 12px; text-transform: uppercase; letter-spacing: 0.05em; }

/* Cards */
.card {
  background: var(--surface);
  border: 1px solid var(--border);
  border-radius: 10px;
  padding: 20px;
}
.card h2 { font-size: 14px; font-weight: 600; margin-bottom: 16px; color: var(--text-muted); text-transform: uppercase; letter-spacing: 0.05em; }

/* Two col */
.two-col { display: grid; grid-template-columns: 1fr 1fr; gap: 20px; }
@media (max-width: 700px) { .two-col { grid-template-columns: 1fr; } }

/* Job control */
.controls { display: flex; gap: 10px; margin-bottom: 10px; }
.controls input {
  flex: 1; padding: 8px 12px; background: var(--bg); border: 1px solid var(--border);
  border-radius: 6px; color: var(--text); font-size: 14px;
}
.controls input:focus { outline: none; border-color: var(--indigo); }

.btn-primary {
  padding: 8px 16px; background: var(--indigo); color: white;
  border: none; border-radius: 6px; cursor: pointer; font-size: 14px; white-space: nowrap;
}
.btn-primary:disabled { opacity: 0.5; cursor: not-allowed; }
.btn-primary:not(:disabled):hover { background: #4f46e5; }

.quick-btns { display: flex; gap: 6px; flex-wrap: wrap; }
.btn-ghost {
  padding: 4px 10px; background: transparent; border: 1px solid var(--border);
  border-radius: 6px; color: var(--text-muted); cursor: pointer; font-size: 12px;
}
.btn-ghost:hover { border-color: var(--indigo); color: var(--text); }

.result { margin-top: 12px; padding: 8px 12px; border-radius: 6px; font-size: 13px; }
.result.success { background: rgba(16,185,129,0.1); color: var(--green); }
.result.error   { background: rgba(239,68,68,0.1);  color: var(--red); }

.fade-enter-active, .fade-leave-active { transition: opacity 0.3s; }
.fade-enter-from, .fade-leave-to { opacity: 0; }

/* Worker status */
.worker-status { display: flex; flex-direction: column; gap: 12px; }
.worker-idle { display: flex; align-items: center; gap: 10px; color: var(--text-muted); padding: 12px 0; }
.worker-list { display: flex; flex-direction: column; gap: 8px; }
.worker-item { display: flex; align-items: center; gap: 10px; padding: 8px 12px; background: rgba(16,185,129,0.08); border: 1px solid rgba(16,185,129,0.2); border-radius: 6px; }
.worker-icon { font-size: 18px; }
.spinning { display: inline-block; animation: spin 2s linear infinite; }
@keyframes spin { from { transform: rotate(0deg); } to { transform: rotate(360deg); } }
.worker-hint { font-size: 12px; color: var(--text-muted); margin-top: auto; }
.worker-hint code { background: var(--bg); padding: 2px 6px; border-radius: 4px; }
</style>
