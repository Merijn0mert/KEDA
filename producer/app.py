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

# In-memory metrics history (laatste 120 datapunten = 2 minuten bij 1s interval)
metrics_history = deque(maxlen=120)
metrics_lock = threading.Lock()


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
    try:
        import urllib.request, base64
        url = f"http://{RABBITMQ_HOST}:{RABBITMQ_MGMT_PORT}/api/queues/%2F/{QUEUE_NAME}"
        req = urllib.request.Request(url)
        creds = base64.b64encode(f"{RABBITMQ_USER}:{RABBITMQ_PASS}".encode()).decode()
        req.add_header("Authorization", f"Basic {creds}")
        with urllib.request.urlopen(req, timeout=2) as resp:
            data = json.loads(resp.read())
            return data.get("messages", 0)
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


def collect_metrics():
    """Achtergrond thread die elke seconde metrics verzamelt."""
    while True:
        point = {
            "timestamp": time.time(),
            "queue_length": get_queue_length(),
            "consumers": get_consumer_count(),
            "cpu_percent": psutil.cpu_percent(interval=None),
            "memory_mb": psutil.Process().memory_info().rss / 1024 / 1024,
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

    t_start = time.time()
    try:
        connection = get_connection()
        channel = connection.channel()
        channel.queue_declare(queue=QUEUE_NAME, durable=True)

        for _ in range(body.count):
            payload = json.dumps({"job_id": str(uuid.uuid4()), "created_at": time.time()})
            channel.basic_publish(
                exchange="",
                routing_key=QUEUE_NAME,
                body=payload,
                properties=pika.BasicProperties(delivery_mode=2),
            )

        connection.close()
    except Exception as e:
        raise HTTPException(status_code=503, detail=f"RabbitMQ error: {e}")

    return {
        "queued": body.count,
        "publish_time_ms": round((time.time() - t_start) * 1000, 2),
    }


@app.get("/metrics/current")
def metrics_current():
    queue_length = get_queue_length()
    consumers = get_consumer_count()
    return {
        "timestamp": time.time(),
        "queue_length": queue_length,
        "consumers": consumers,
        "cpu_percent": psutil.cpu_percent(interval=None),
        "memory_mb": round(psutil.Process().memory_info().rss / 1024 / 1024, 2),
    }


@app.get("/metrics/history")
def metrics_history_endpoint():
    with metrics_lock:
        return list(metrics_history)


@app.get("/healthz")
def healthz():
    return {"status": "ok"}
