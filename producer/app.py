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

RABBITMQ_HOST = os.environ.get("RABBITMQ_HOST", "rabbitmq")
RABBITMQ_PORT = int(os.environ.get("RABBITMQ_PORT", "5672"))
RABBITMQ_USER = os.environ.get("RABBITMQ_USER", "guest")
RABBITMQ_PASS = os.environ.get("RABBITMQ_PASS", "guest")
RABBITMQ_MGMT_PORT = int(os.environ.get("RABBITMQ_MGMT_PORT", "15672"))
QUEUE_NAME = os.environ.get("QUEUE_NAME", "jobs")

metrics_history = deque(maxlen=120)
metrics_lock = threading.Lock()

# --- Run-based state ---
# Een "run" = 1 batch jobs die via /add-job is gepost.
# We resetten total_jobs en de timer telkens als er een NIEUWE
# batch wordt gestart op het moment dat de vorige run al klaar is
# (of als het de allereerste batch is).
run_lock = threading.Lock()
run_state = {
    "jobs_in_run": 0,        # hoeveel jobs zijn er in de huidige batch gepost
    "jobs_completed_in_run": 0,  # hoeveel daarvan zijn klaar
    "start_time": None,
    "end_time": None,
    "peak_workers": 0,
}

# Lifetime totals (optioneel, voor eventuele andere weergave)
central_metrics = {
    "total_jobs": 0,
    "total_processing_time_ms": 0,
}

# Laatste gerapporteerde CPU/geheugen per worker, met timestamp.
# We tonen het gemiddelde van alle workers die "recent" (binnen
# WORKER_STATS_TTL seconden) iets hebben gerapporteerd. Zo telt een
# gestopte worker niet eeuwig door mee in het gemiddelde.
worker_stats_lock = threading.Lock()
worker_stats = {}  # worker_id -> {"cpu_percent": float, "memory_mb": float, "last_seen": float}
WORKER_STATS_TTL = 15  # seconden; ruim boven PROCESSING_TIME zodat actieve workers niet wegvallen tussen jobs

# Actieve workers: instant bijgehouden via expliciete online/offline
# meldingen van de workers zelf (i.p.v. RabbitMQ's consumers-telling
# via de Management API, die een polling-vertraging heeft).
active_workers_lock = threading.Lock()
active_workers = {}  # worker_id -> last_seen timestamp
ACTIVE_WORKER_TTL = 20  # vangnet: als een worker crasht zonder offline te melden, valt hij na deze tijd alsnog weg


def get_connection():
    credentials = pika.PlainCredentials(RABBITMQ_USER, RABBITMQ_PASS)
    parameters = pika.ConnectionParameters(
        host=RABBITMQ_HOST,
        port=RABBITMQ_PORT,
        credentials=credentials,
        heartbeat=30,
        blocked_connection_timeout=10,
        connection_attempts=3,
        retry_delay=2,
    )
    return pika.BlockingConnection(parameters)


def get_queue_length() -> int:
    # We gebruiken hier de AMQP-verbinding zelf (passive queue_declare)
    # in plaats van de Management API. De Management API houdt queue-
    # statistieken bij via een interne collector met een interval
    # (collect_statistics_interval), wat altijd een vertraging geeft,
    # ongeacht hoe laag je dat interval zet. Een passive declare vraagt
    # RabbitMQ rechtstreeks naar de actuele staat van de queue: instant
    # en exact correct.
    try:
        connection = get_connection()
        channel = connection.channel()
        result = channel.queue_declare(queue=QUEUE_NAME, durable=True, passive=True)
        count = result.method.message_count
        connection.close()
        return count
    except Exception:
        return -1


def get_consumer_count() -> int:
    try:
        import urllib.request, base64
        url = f"http://{RABBITMQ_HOST}:{RABBITMQ_MGMT_PORT}/api/queues/%2F/{QUEUE_NAME}"
        req = urllib.request.Request(url)
        creds = base64.b64encode(f"{RABBITMQ_USER}:{RABBITMQ_PASS}".encode()).decode()
        req.add_header("Authorization", f"Basic {creds}")
        with urllib.request.urlopen(req, timeout=2) as resp:
            data = json.loads(resp.read())
            return data.get("consumers", 0)
    except Exception:
        return 0


def get_active_worker_count() -> int:
    now = time.time()
    with active_workers_lock:
        stale = [wid for wid, last_seen in active_workers.items() if now - last_seen > ACTIVE_WORKER_TTL]
        for wid in stale:
            del active_workers[wid]
        return len(active_workers)


def get_avg_worker_stats():
    now = time.time()
    with worker_stats_lock:
        # ruim verouderde entries op
        stale = [wid for wid, s in worker_stats.items() if now - s["last_seen"] > WORKER_STATS_TTL]
        for wid in stale:
            del worker_stats[wid]

        if not worker_stats:
            return 0.0, 0.0

        cpu_avg = sum(s["cpu_percent"] for s in worker_stats.values()) / len(worker_stats)
        mem_avg = sum(s["memory_mb"] for s in worker_stats.values()) / len(worker_stats)
        return round(cpu_avg, 2), round(mem_avg, 2)


def collect_metrics():
    while True:
        consumers = get_active_worker_count()

        with run_lock:
            if consumers > run_state["peak_workers"]:
                run_state["peak_workers"] = consumers

        cpu_avg, mem_avg = get_avg_worker_stats()

        point = {
            "timestamp": time.time(),
            "queue_length": get_queue_length(),
            "consumers": consumers,
            # CPU/geheugen van de WORKERS (gemiddeld over actieve workers),
            # niet van de producer zelf — dat is voor autoscaling-inzicht
            # de relevante metric.
            "cpu_percent": cpu_avg,
            "memory_mb": mem_avg,
        }

        with metrics_lock:
            metrics_history.append(point)

        time.sleep(1)


threading.Thread(target=collect_metrics, daemon=True).start()


class AddJobRequest(BaseModel):
    count: int = 1


@app.post("/add-job")
def add_job(body: AddJobRequest):
    if body.count < 1:
        raise HTTPException(status_code=400, detail="count must be >= 1")
    if body.count > 10000:
        raise HTTPException(status_code=400, detail="count too large (max 10000)")

    with run_lock:
        # Nieuwe run: reset alles. Dit start altijd een verse meting
        # voor de batch die je nu toevoegt.
        run_state["jobs_in_run"] = body.count
        run_state["jobs_completed_in_run"] = 0
        run_state["start_time"] = time.time()
        run_state["end_time"] = None
        run_state["peak_workers"] = get_active_worker_count()

    publish_start = time.time()
    try:
        connection = get_connection()
        channel = connection.channel()
        channel.queue_declare(queue=QUEUE_NAME, durable=True)

        for _ in range(body.count):
            job_id = str(uuid.uuid4())
            message = json.dumps({
                "job_id": job_id,
                "created_at": time.time(),
            })
            channel.basic_publish(
                exchange="",
                routing_key=QUEUE_NAME,
                body=message,
                properties=pika.BasicProperties(delivery_mode=2),
            )

        connection.close()
    except Exception as e:
        raise HTTPException(status_code=503, detail=f"kon jobs niet publiceren: {e}")

    publish_time_ms = round((time.time() - publish_start) * 1000, 2)

    return {
        "status": "ok",
        "jobs_added": body.count,
        "queued": body.count,
        "publish_time_ms": publish_time_ms,
    }


class WorkerPing(BaseModel):
    worker_id: str


@app.post("/worker/online")
def worker_online(body: WorkerPing):
    with active_workers_lock:
        active_workers[body.worker_id] = time.time()
    return {"status": "ok"}


@app.post("/worker/offline")
def worker_offline(body: WorkerPing):
    with active_workers_lock:
        active_workers.pop(body.worker_id, None)
    return {"status": "ok"}


@app.get("/metrics/current")
def metrics_current():
    queue_length = get_queue_length()
    consumers = get_active_worker_count()

    # Actieve jobs = jobs die nog niet klaar zijn, minus jobs die nog
    # in de queue liggen (nog niet opgepakt door een worker).
    # Beide queue_length (AMQP, instant) en de run-counters (in-memory,
    # instant) hebben geen polling-vertraging, dus dit getal is altijd
    # actueel zonder afhankelijk te zijn van de Management API.
    with run_lock:
        jobs_remaining = run_state["jobs_in_run"] - run_state["jobs_completed_in_run"]
    active_jobs = max(0, jobs_remaining - max(0, queue_length))

    cpu_avg, mem_avg = get_avg_worker_stats()

    return {
        "timestamp": time.time(),
        "queue_length": queue_length,
        "consumers": consumers,
        "active_jobs": active_jobs,
        "cpu_percent": cpu_avg,
        "memory_mb": mem_avg,
    }


@app.get("/metrics/history")
def metrics_history_endpoint():
    with metrics_lock:
        return list(metrics_history)


@app.post("/metrics/update")
def update_metrics(data: dict):
    global central_metrics
    print("UPDATE RECEIVED:", data)

    central_metrics["total_jobs"] += data.get("jobs", 0)
    central_metrics["total_processing_time_ms"] += data.get("processing_time", 0)

    worker_id = data.get("worker_id")
    if worker_id:
        with worker_stats_lock:
            worker_stats[worker_id] = {
                "cpu_percent": data.get("cpu_percent", 0.0),
                "memory_mb": data.get("memory_mb", 0.0),
                "last_seen": time.time(),
            }
        with active_workers_lock:
            # Alleen verversen als de worker al als 'online' geregistreerd
            # staat; dit voorkomt dat een offline-gemelde worker per
            # ongeluk weer als actief gaat tellen door een late update-call.
            if worker_id in active_workers:
                active_workers[worker_id] = time.time()

    with run_lock:
        run_state["jobs_completed_in_run"] += data.get("jobs", 0)

        # Run is pas klaar als ALLE jobs van DEZE batch verwerkt zijn
        if (
            run_state["start_time"] is not None
            and run_state["end_time"] is None
            and run_state["jobs_completed_in_run"] >= run_state["jobs_in_run"]
        ):
            run_state["end_time"] = time.time()

    return {"status": "ok"}


@app.get("/metrics/summary")
def metrics_summary():
    with run_lock:
        if run_state["start_time"] is None:
            system_time = {"status": "no jobs yet"}
        elif run_state["end_time"] is None:
            system_time = {
                "status": "running",
                "elapsed_seconds": time.time() - run_state["start_time"]
            }
        else:
            system_time = {
                "status": "completed",
                "total_time_seconds": run_state["end_time"] - run_state["start_time"]
            }

        jobs_completed_in_run = run_state["jobs_completed_in_run"]
        peak_workers = run_state["peak_workers"]

    return {
        "timestamp": time.time(),
        "total_jobs": jobs_completed_in_run,
        "total_processing_time_ms": central_metrics["total_processing_time_ms"],
        "consumers": get_active_worker_count(),
        "peak_workers": peak_workers,
        "system_time": system_time
    }


@app.get("/healthz")
def healthz():
    return {"status": "ok"}