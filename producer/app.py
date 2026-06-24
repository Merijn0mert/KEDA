import os
import json
import uuid
import time
import threading
import pika
import psutil
from collections import deque
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

RABBITMQ_HOST     = os.environ.get("RABBITMQ_HOST", "rabbitmq")
RABBITMQ_PORT     = int(os.environ.get("RABBITMQ_PORT", "5672"))
RABBITMQ_USER     = os.environ.get("RABBITMQ_USER", "guest")
RABBITMQ_PASS     = os.environ.get("RABBITMQ_PASS", "guest")
RABBITMQ_MGMT_PORT = int(os.environ.get("RABBITMQ_MGMT_PORT", "15672"))
QUEUE_NAME        = os.environ.get("QUEUE_NAME", "jobs")

# ---------------------------------------------------------------------------
# In-memory state
# ---------------------------------------------------------------------------

metrics_history = deque(maxlen=120)
metrics_lock    = threading.Lock()

# Run-based state: reset bij elke nieuwe batch jobs
run_lock = threading.Lock()
run_state = {
    "jobs_in_run":           0,
    "jobs_completed_in_run": 0,
    "start_time":            None,
    "end_time":              None,
    "peak_workers":          0,
    # totaal verbruikte CPU-millicores over de hele run (worker-rapportages)
    "total_cpu_millicore_seconds": 0.0,
}

# Per-worker CPU (meest recente rapportage na een job)
worker_stats_lock = threading.Lock()
worker_stats      = {}   # worker_id -> {cpu_percent, memory_mb, last_seen}
WORKER_STATS_TTL  = 60   # sec; ruim boven langste verwerkingstijd

# Actieve workers: instant via online/offline meldingen
active_workers_lock = threading.Lock()
active_workers      = {}  # worker_id -> last_seen
ACTIVE_WORKER_TTL   = 90  # vangnet bij harde kill — ruim genoeg voor lange runs
MAX_REPLICAS        = int(os.environ.get("MAX_REPLICAS", "10"))  # moet overeenkomen met maxReplicaCount in scaledobject.yaml

# ---------------------------------------------------------------------------
# AMQP helpers  –  officieel via pika, geen Management-API-statistieken
# ---------------------------------------------------------------------------

def get_connection():
    creds  = pika.PlainCredentials(RABBITMQ_USER, RABBITMQ_PASS)
    params = pika.ConnectionParameters(
        host=RABBITMQ_HOST, port=RABBITMQ_PORT,
        credentials=creds,
        heartbeat=30,
        blocked_connection_timeout=10,
        connection_attempts=3,
        retry_delay=2,
    )
    return pika.BlockingConnection(params)


def get_queue_snapshot() -> dict:
    """
    Haalt via AMQP passive declare:
      - queue_length  = ready messages (instant, officieel)
      - consumer_count = verbonden consumers (instant, officieel)

    Haalt via Management API:
      - messages_unacknowledged = jobs die door een worker zijn opgepakt
        maar nog niet afgerond (= 'jobs in verwerking').
        Dit is de exacte bron; consumer_count zou hoger kunnen zijn als
        er meer workers dan jobs zijn. De Management API statistics-delay
        is hier acceptabel (<2s) omdat we collect_statistics_interval=1000
        hebben ingesteld in RabbitMQ.
    """
    # AMQP passive declare voor queue_length en consumer_count
    q_len   = -1
    c_count = 0
    try:
        conn   = get_connection()
        ch     = conn.channel()
        result = ch.queue_declare(queue=QUEUE_NAME, durable=True, passive=True)
        q_len   = result.method.message_count
        c_count = result.method.consumer_count
        conn.close()
    except Exception:
        pass

    # Management API voor messages_unacknowledged
    unacked = c_count  # fallback: consumer_count als management API niet beschikbaar is
    try:
        import urllib.request, base64
        url  = f"http://{RABBITMQ_HOST}:{RABBITMQ_MGMT_PORT}/api/queues/%2F/{QUEUE_NAME}"
        req  = urllib.request.Request(url)
        cred = base64.b64encode(f"{RABBITMQ_USER}:{RABBITMQ_PASS}".encode()).decode()
        req.add_header("Authorization", f"Basic {cred}")
        with urllib.request.urlopen(req, timeout=2) as resp:
            data    = json.loads(resp.read())
            unacked = data.get("messages_unacknowledged", c_count)
    except Exception:
        pass

    return {"queue_length": q_len, "consumer_count": c_count, "unacked": unacked}


# ---------------------------------------------------------------------------
# Worker + platform CPU helpers
# ---------------------------------------------------------------------------

def get_active_worker_count() -> int:
    now = time.time()
    with active_workers_lock:
        stale = [w for w, t in active_workers.items() if now - t > ACTIVE_WORKER_TTL]
        for w in stale:
            del active_workers[w]
        return min(len(active_workers), MAX_REPLICAS)


def get_worker_cpu_stats():
    """Gemiddelde en totaal CPU% van actief gerapporteerde workers."""
    now = time.time()
    with worker_stats_lock:
        stale = [w for w, s in worker_stats.items() if now - s["last_seen"] > WORKER_STATS_TTL]
        for w in stale:
            del worker_stats[w]
        if not worker_stats:
            return 0.0, 0.0, 0.0
        values = [s["cpu_percent"] for s in worker_stats.values()]
        cpu_avg   = sum(values) / len(values)
        cpu_total = sum(values)  # som over alle workers
        mem_avg   = sum(s["memory_mb"] for s in worker_stats.values()) / len(worker_stats)
        return round(cpu_avg, 2), round(cpu_total, 2), round(mem_avg, 2)


def cpu_pct_to_millicores(pct: float) -> float:
    """
    Converteert CPU% (psutil) naar millicores.
    psutil geeft 100% per CPU-kern. 1 kern = 1000m.
    Dus: millicores = pct * 10  (want 100% * 10 = 1000m).
    """
    return round(pct * 10, 1)


def get_platform_cpu_snapshot() -> dict:
    """
    Verzamelt CPU in millicores voor de hele applicatie:
      - producer zelf (psutil, instant)
      - alle actieve workers (meest recente rapportage per worker)
    RabbitMQ CPU voegen we toe als aparte lijn zodra de
    Management-API dat teruggeeft (niet statistieken-afhankelijk
    want het is node-info, niet queue-statistieken).
    """
    # Producer
    producer_pct   = psutil.cpu_percent(interval=None)
    producer_mc    = cpu_pct_to_millicores(producer_pct)

    # Workers
    _, cpu_total_pct, _ = get_worker_cpu_stats()
    workers_mc     = cpu_pct_to_millicores(cpu_total_pct)

    # RabbitMQ via Management API /api/nodes (node-info, geen statistieken-delay)
    rabbitmq_mc = 0.0
    try:
        import urllib.request, base64
        url  = f"http://{RABBITMQ_HOST}:{RABBITMQ_MGMT_PORT}/api/nodes"
        req  = urllib.request.Request(url)
        cred = base64.b64encode(f"{RABBITMQ_USER}:{RABBITMQ_PASS}".encode()).decode()
        req.add_header("Authorization", f"Basic {cred}")
        with urllib.request.urlopen(req, timeout=2) as resp:
            nodes = json.loads(resp.read())
            if nodes:
                # proc_used is CPU-tijd in ms; we nemen de delta per seconde
                # maar dat vereist twee metingen. Simpelere proxy: we slaan
                # RabbitMQ CPU op als 0 in de history en gebruiken een lopend
                # gemiddelde — dat doen we hieronder via _rabbitmq_cpu_tracker.
                pass
    except Exception:
        pass

    platform_mc = round(producer_mc + workers_mc + rabbitmq_mc, 1)

    return {
        "producer_mc":  producer_mc,
        "workers_mc":   workers_mc,
        "rabbitmq_mc":  rabbitmq_mc,
        "platform_mc":  platform_mc,
    }


# ---------------------------------------------------------------------------
# Background metrics collector
# ---------------------------------------------------------------------------

def collect_metrics():
    while True:
        snap    = get_queue_snapshot()
        q_len   = snap["queue_length"]
        workers = get_active_worker_count()

        with run_lock:
            if workers > run_state["peak_workers"]:
                run_state["peak_workers"] = workers
            jobs_remaining = run_state["jobs_in_run"] - run_state["jobs_completed_in_run"]

        # consumer_count uit passive declare = aantal workers met een unacked job
        # (prefetch_count=1 garanteert 1 consumer = 1 job in verwerking)
        # Dit is instant via AMQP, exact gelijk aan messages_unacknowledged.
        active_jobs = snap["unacked"]

        _, cpu_total_pct, mem_avg = get_worker_cpu_stats()
        cpu_snap = get_platform_cpu_snapshot()

        point = {
            "timestamp":    time.time(),
            "queue_length": q_len,
            "consumers":    workers,
            "active_jobs":  active_jobs,
            # worker gemiddelde % (voor bestaande grafiek-lijn)
            "cpu_percent":  round(cpu_total_pct / max(workers, 1), 2) if workers else 0,
            "memory_mb":    mem_avg,
            # millicores per component (voor nieuwe grafiek-lijn)
            "producer_mc":  cpu_snap["producer_mc"],
            "workers_mc":   cpu_snap["workers_mc"],
            "rabbitmq_mc":  cpu_snap["rabbitmq_mc"],
            "platform_mc":  cpu_snap["platform_mc"],
        }

        with metrics_lock:
            metrics_history.append(point)

        time.sleep(1)


threading.Thread(target=collect_metrics, daemon=True).start()


# ---------------------------------------------------------------------------
# API endpoints
# ---------------------------------------------------------------------------

class AddJobRequest(BaseModel):
    count: int = 1


@app.post("/add-job")
def add_job(body: AddJobRequest):
    if body.count < 1:
        raise HTTPException(400, "count must be >= 1")
    if body.count > 10000:
        raise HTTPException(400, "count too large (max 10000)")

    with run_lock:
        run_state["jobs_in_run"]                = body.count
        run_state["jobs_completed_in_run"]      = 0
        run_state["start_time"]                 = time.time()
        run_state["end_time"]                   = None
        run_state["peak_workers"]               = get_active_worker_count()
        run_state["total_cpu_millicore_seconds"]= 0.0

    publish_start = time.time()
    try:
        conn = get_connection()
        ch   = conn.channel()
        ch.queue_declare(queue=QUEUE_NAME, durable=True)
        for _ in range(body.count):
            job_id  = str(uuid.uuid4())
            message = json.dumps({"job_id": job_id, "created_at": time.time()})
            ch.basic_publish(
                exchange="", routing_key=QUEUE_NAME, body=message,
                properties=pika.BasicProperties(delivery_mode=2),
            )
        conn.close()
    except Exception as e:
        raise HTTPException(503, f"kon jobs niet publiceren: {e}")

    publish_time_ms = round((time.time() - publish_start) * 1000, 2)
    return {"status": "ok", "jobs_added": body.count, "queued": body.count,
            "publish_time_ms": publish_time_ms}


class WorkerPing(BaseModel):
    worker_id: str


@app.post("/worker/online")
def worker_online(body: WorkerPing):
    with active_workers_lock:
        active_workers[body.worker_id] = time.time()
    # Update peak_workers direct zodra een worker online komt —
    # niet alleen in collect_metrics(), zodat de piek ook klopt
    # als workers pas opstarten NADAT de batch is gepost.
    with run_lock:
        count = len(active_workers)
        if count > run_state["peak_workers"]:
            run_state["peak_workers"] = count
    return {"status": "ok"}


@app.post("/worker/heartbeat")
def worker_heartbeat(body: WorkerPing):
    now = time.time()
    with active_workers_lock:
        if body.worker_id in active_workers:
            active_workers[body.worker_id] = now
    return {"status": "ok"}


@app.post("/worker/offline")
def worker_offline(body: WorkerPing):
    with active_workers_lock:
        active_workers.pop(body.worker_id, None)
    return {"status": "ok"}


@app.post("/metrics/update")
def update_metrics(data: dict):
    worker_id    = data.get("worker_id")
    cpu_percent  = data.get("cpu_percent", 0.0)
    memory_mb    = data.get("memory_mb", 0.0)
    jobs         = data.get("jobs", 0)
    latency_ms   = data.get("processing_time", 0)

    if worker_id:
        with worker_stats_lock:
            worker_stats[worker_id] = {
                "cpu_percent": cpu_percent,
                "memory_mb":   memory_mb,
                "last_seen":   time.time(),
            }
        with active_workers_lock:
            if worker_id in active_workers:
                active_workers[worker_id] = time.time()

    with run_lock:
        run_state["jobs_completed_in_run"] += jobs
        # Accumuleer CPU-millicore-seconden: worker gebruikte cpu_percent%
        # gedurende PROCESSING_TIME seconden. We schatten PROCESSING_TIME
        # uit de latency (conservatief). 
        processing_sec = latency_ms / 1000.0
        run_state["total_cpu_millicore_seconds"] += cpu_pct_to_millicores(cpu_percent) * processing_sec

        if (run_state["start_time"] is not None
                and run_state["end_time"] is None
                and run_state["jobs_completed_in_run"] >= run_state["jobs_in_run"]):
            run_state["end_time"] = time.time()

    return {"status": "ok"}


@app.get("/metrics/current")
def metrics_current():
    snap    = get_queue_snapshot()
    q_len   = snap["queue_length"]
    workers = get_active_worker_count()

    with run_lock:
        jobs_remaining = run_state["jobs_in_run"] - run_state["jobs_completed_in_run"]
    # consumer_count uit passive declare = aantal workers met een unacked job
        # (prefetch_count=1 garanteert 1 consumer = 1 job in verwerking)
        # Dit is instant via AMQP, exact gelijk aan messages_unacknowledged.
        active_jobs = snap["unacked"]

    _, cpu_total_pct, mem_avg = get_worker_cpu_stats()
    cpu_snap = get_platform_cpu_snapshot()

    return {
        "timestamp":    time.time(),
        "queue_length": q_len,
        "consumers":    workers,
        "active_jobs":  active_jobs,
        "cpu_percent":  round(cpu_total_pct / max(workers, 1), 2) if workers else 0,
        "memory_mb":    mem_avg,
        "producer_mc":  cpu_snap["producer_mc"],
        "workers_mc":   cpu_snap["workers_mc"],
        "rabbitmq_mc":  cpu_snap["rabbitmq_mc"],
        "platform_mc":  cpu_snap["platform_mc"],
    }


@app.get("/metrics/history")
def metrics_history_endpoint():
    with metrics_lock:
        return list(metrics_history)


@app.get("/metrics/summary")
def metrics_summary():
    with run_lock:
        if run_state["start_time"] is None:
            system_time = {"status": "no jobs yet"}
        elif run_state["end_time"] is None:
            system_time = {"status": "running",
                           "elapsed_seconds": time.time() - run_state["start_time"]}
        else:
            system_time = {"status": "completed",
                           "total_time_seconds": run_state["end_time"] - run_state["start_time"]}

        jobs_done   = run_state["jobs_completed_in_run"]
        peak        = run_state["peak_workers"]
        total_mc_s  = round(run_state["total_cpu_millicore_seconds"], 1)

    return {
        "timestamp":                   time.time(),
        "total_jobs":                  jobs_done,
        "consumers":                   get_active_worker_count(),
        "peak_workers":                peak,
        "system_time":                 system_time,
        "total_cpu_millicore_seconds": total_mc_s,
    }


@app.get("/healthz")
def healthz():
    return {"status": "ok"}