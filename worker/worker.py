"""
TaskFlow Worker
Pulls jobs from the Redis 'task_queue' list, simulates processing,
and updates the task status in Postgres.
"""
import json
import os
import time
import random
import signal
import sys
import logging
import psycopg2
import redis
from dotenv import load_dotenv

load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [worker] %(levelname)s %(message)s",
    datefmt="%Y-%m-%dT%H:%M:%S",
)
log = logging.getLogger(__name__)

# ── Config ─────────────────────────────────────────────────────────────────────
REDIS_HOST     = os.getenv("REDIS_HOST", "localhost")
REDIS_PORT     = int(os.getenv("REDIS_PORT", 6379))
POSTGRES_HOST  = os.getenv("POSTGRES_HOST", "localhost")
POSTGRES_PORT  = int(os.getenv("POSTGRES_PORT", 5432))
POSTGRES_DB    = os.getenv("POSTGRES_DB", "taskflow")
POSTGRES_USER  = os.getenv("POSTGRES_USER", "taskflow")
POSTGRES_PASS  = os.getenv("POSTGRES_PASSWORD", "taskflow")

# ── Graceful shutdown ──────────────────────────────────────────────────────────
running = True

def handle_signal(sig, frame):
    global running
    log.info("Shutdown signal received, finishing current job…")
    running = False

signal.signal(signal.SIGTERM, handle_signal)
signal.signal(signal.SIGINT, handle_signal)

# ── Connections ────────────────────────────────────────────────────────────────
def connect_redis(retries=10):
    for i in range(retries):
        try:
            r = redis.Redis(host=REDIS_HOST, port=REDIS_PORT, decode_responses=True)
            r.ping()
            log.info("Connected to Redis")
            return r
        except redis.ConnectionError:
            log.warning(f"Redis not ready, retrying ({i+1}/{retries})…")
            time.sleep(2)
    raise RuntimeError("Could not connect to Redis")

def connect_db(retries=10):
    for i in range(retries):
        try:
            conn = psycopg2.connect(
                host=POSTGRES_HOST, port=POSTGRES_PORT,
                dbname=POSTGRES_DB, user=POSTGRES_USER, password=POSTGRES_PASS,
            )
            log.info("Connected to Postgres")
            return conn
        except psycopg2.OperationalError:
            log.warning(f"DB not ready, retrying ({i+1}/{retries})…")
            time.sleep(2)
    raise RuntimeError("Could not connect to Postgres")

# ── Task processing ────────────────────────────────────────────────────────────
def process_task(task: dict) -> str:
    """
    Simulates real work: sleeps 1–4 seconds, then returns a result string.
    Replace this with your actual business logic.
    """
    duration = random.uniform(1, 4)
    log.info(f"Processing task {task['id']} — '{task['title']}' (~{duration:.1f}s)")
    time.sleep(duration)
    return f"Completed '{task['title']}' in {duration:.2f}s"

def update_task(conn, task_id: str, status: str, result: str = None):
    with conn.cursor() as cur:
        cur.execute(
            """
            UPDATE tasks
            SET status = %s, result = %s, updated_at = NOW()
            WHERE id = %s
            """,
            (status, result, task_id),
        )
    conn.commit()

# ── Main loop ──────────────────────────────────────────────────────────────────
def main():
    r = connect_redis()
    conn = connect_db()

    log.info("Worker ready — listening on 'task_queue'")

    while running:
        try:
            # BRPOP blocks for up to 2s, returns (queue_name, value) or None
            item = r.brpop("task_queue", timeout=2)
            if item is None:
                continue  # timeout, loop again to check `running`

            _, raw = item
            task = json.loads(raw)

            # Mark as processing
            update_task(conn, task["id"], "processing")

            try:
                result = process_task(task)
                update_task(conn, task["id"], "done", result)
                log.info(f"Task {task['id']} → done")
            except Exception as err:
                update_task(conn, task["id"], "failed", str(err))
                log.error(f"Task {task['id']} → failed: {err}")

        except (psycopg2.InterfaceError, psycopg2.OperationalError):
            log.warning("DB connection lost, reconnecting…")
            conn = connect_db()
        except Exception as err:
            log.error(f"Unexpected error: {err}")
            time.sleep(1)

    log.info("Worker shut down cleanly")
    conn.close()

if __name__ == "__main__":
    main()
