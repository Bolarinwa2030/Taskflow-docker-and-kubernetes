# TaskFlow — DevOps Portfolio Project

A three-service task queue application designed to be containerised,
deployed to Kubernetes with Helm, and monitored with Prometheus + Grafana.

## Architecture

```
frontend (nginx) ──→ api (Node.js/Express) ──→ postgres
                          │
                          └──→ redis ←── worker (Python)
```

| Service  | Language | Role |
|----------|----------|------|
| api      | Node.js  | Receives HTTP requests, writes tasks to Postgres, pushes to Redis |
| worker   | Python   | Pulls tasks from Redis, processes them, updates Postgres |
| frontend | nginx    | Serves the HTML/JS UI, proxies `/api` to the API service |

## Quick start (Docker Compose)

```bash
# 1. Clone the repo
git clone <your-repo> taskflow && cd taskflow

# 2. Create your env file
cp .env.example .env

# 3. Build and start all services
docker compose up --build

# 4. Open the UI
open http://localhost:8080

# 5. Scale the worker (optional)
docker compose up --scale worker=3
```

## API endpoints

| Method | Path        | Description          |
|--------|-------------|----------------------|
| GET    | /health     | Health check         |
| GET    | /tasks      | List all tasks       |
| GET    | /tasks/:id  | Get a single task    |
| POST   | /tasks      | Create a new task    |
| GET    | /stats      | Counts by status     |

### Create a task (example)

```bash
curl -X POST http://localhost:3000/tasks \
  -H "Content-Type: application/json" \
  -d '{"title": "process report", "payload": "{\"month\": \"june\"}"}'
```

## Project phases

- **Phase 1** — Containerise (this repo) ✅
- **Phase 2** — Deploy to Kubernetes (`/k8s`)
- **Phase 3** — Package with Helm (`/charts`)
- **Phase 4** — CI/CD + Observability (`.github/workflows`)
