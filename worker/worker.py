import os
import json
import time
import signal
import pika
import psutil

RABBITMQ_HOST = os.environ.get("RABBITMQ_HOST", "rabbitmq")
RABBITMQ_PORT = int(os.environ.get("RABBITMQ_PORT", "5672"))
RABBITMQ_USER = os.environ.get("RABBITMQ_USER", "guest")
RABBITMQ_PASS = os.environ.get("RABBITMQ_PASS", "guest")
QUEUE_NAME    = os.environ.get("QUEUE_NAME", "jobs")
PROCESSING_TIME = float(os.environ.get("PROCESSING_TIME_SECONDS", "5"))

WORKER_ID = os.environ.get("HOSTNAME", "worker-local")

_shutdown = False

def handle_signal(signum, frame):
    global _shutdown
    print(f"[{WORKER_ID}] shutdown signaal ontvangen", flush=True)
    _shutdown = True

signal.signal(signal.SIGTERM, handle_signal)
signal.signal(signal.SIGINT, handle_signal)


def get_connection():
    credentials = pika.PlainCredentials(RABBITMQ_USER, RABBITMQ_PASS)
    params = pika.ConnectionParameters(
        host=RABBITMQ_HOST,
        port=RABBITMQ_PORT,
        credentials=credentials,
        heartbeat=30,
        blocked_connection_timeout=10,
        connection_attempts=5,
        retry_delay=3,
    )
    return pika.BlockingConnection(params)


def callback(ch, method, properties, body):
    t_start = time.time()
    try:
        payload = json.loads(body)
        job_id = payload.get("job_id", "unknown")
        created_at = payload.get("created_at", t_start)
    except Exception:
        job_id = "unparseable"
        created_at = t_start

    wait_time = round((t_start - created_at) * 1000, 2)
    print(f"[{WORKER_ID}] ▶ job {job_id} | wachttijd in queue: {wait_time}ms", flush=True)

    cpu_before = psutil.cpu_percent(interval=None)
    time.sleep(PROCESSING_TIME)
    cpu_after = psutil.cpu_percent(interval=None)

    duration = round((time.time() - t_start) * 1000, 2)
    print(
        f"[{WORKER_ID}] ✓ job {job_id} | verwerkt in {duration}ms | "
        f"cpu: {cpu_before}% → {cpu_after}%",
        flush=True,
    )

    ch.basic_ack(delivery_tag=method.delivery_tag)

    if _shutdown:
        ch.stop_consuming()


def main():
    print(f"[{WORKER_ID}] verbinden met RabbitMQ op {RABBITMQ_HOST}:{RABBITMQ_PORT}...", flush=True)

    while True:
        try:
            connection = get_connection()
            channel = connection.channel()
            channel.queue_declare(queue=QUEUE_NAME, durable=True)
            channel.basic_qos(prefetch_count=1)
            channel.basic_consume(queue=QUEUE_NAME, on_message_callback=callback)
            print(f"[{WORKER_ID}] wachten op jobs in '{QUEUE_NAME}'...", flush=True)
            channel.start_consuming()
        except pika.exceptions.AMQPConnectionError as e:
            if _shutdown:
                break
            print(f"[{WORKER_ID}] verbinding verloren ({e}), opnieuw proberen...", flush=True)
            time.sleep(5)
        except Exception as e:
            print(f"[{WORKER_ID}] fout: {e}", flush=True)
            if _shutdown:
                break
            time.sleep(5)

    print(f"[{WORKER_ID}] gestopt", flush=True)


if __name__ == "__main__":
    main()
