require('dotenv').config();
const express = require('express');
const cors = require('cors');
const { Pool } = require('pg');
const Redis = require('ioredis');
const { v4: uuidv4 } = require('uuid');

const app = express();
app.use(cors());
app.use(express.json());

// ── Database ──────────────────────────────────────────────────────────────────
const db = new Pool({
  host: process.env.POSTGRES_HOST || 'localhost',
  port: process.env.POSTGRES_PORT || 5432,
  database: process.env.POSTGRES_DB || 'taskflow',
  user: process.env.POSTGRES_USER || 'taskflow',
  password: process.env.POSTGRES_PASSWORD || 'taskflow',
});

// ── Redis ─────────────────────────────────────────────────────────────────────
const redis = new Redis({
  host: process.env.REDIS_HOST || 'localhost',
  port: process.env.REDIS_PORT || 6379,
});

// ── DB Init ───────────────────────────────────────────────────────────────────
async function initDB() {
  await db.query(`
    CREATE TABLE IF NOT EXISTS tasks (
      id          UUID PRIMARY KEY,
      title       TEXT NOT NULL,
      payload     TEXT,
      status      TEXT NOT NULL DEFAULT 'queued',
      result      TEXT,
      created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW(),
      updated_at  TIMESTAMPTZ NOT NULL DEFAULT NOW()
    );
  `);
  console.log('Database initialised');
}

// ── Routes ────────────────────────────────────────────────────────────────────

// Health check
app.get('/health', (req, res) => res.json({ status: 'ok', service: 'api' }));

// List all tasks
app.get('/tasks', async (req, res) => {
  try {
    const { rows } = await db.query(
      'SELECT * FROM tasks ORDER BY created_at DESC LIMIT 100'
    );
    res.json(rows);
  } catch (err) {
    console.error(err);
    res.status(500).json({ error: 'Failed to fetch tasks' });
  }
});

// Get single task
app.get('/tasks/:id', async (req, res) => {
  try {
    const { rows } = await db.query('SELECT * FROM tasks WHERE id = $1', [req.params.id]);
    if (!rows.length) return res.status(404).json({ error: 'Task not found' });
    res.json(rows[0]);
  } catch (err) {
    res.status(500).json({ error: 'Failed to fetch task' });
  }
});

// Create a new task
app.post('/tasks', async (req, res) => {
  const { title, payload } = req.body;
  if (!title) return res.status(400).json({ error: 'title is required' });

  const id = uuidv4();
  try {
    await db.query(
      'INSERT INTO tasks (id, title, payload, status) VALUES ($1, $2, $3, $4)',
      [id, title, payload || '', 'queued']
    );

    // Push job onto the Redis queue
    await redis.lpush('task_queue', JSON.stringify({ id, title, payload }));

    const { rows } = await db.query('SELECT * FROM tasks WHERE id = $1', [id]);
    res.status(201).json(rows[0]);
  } catch (err) {
    console.error(err);
    res.status(500).json({ error: 'Failed to create task' });
  }
});

// Stats endpoint
app.get('/stats', async (req, res) => {
  try {
    const { rows } = await db.query(`
      SELECT status, COUNT(*) AS count
      FROM tasks
      GROUP BY status
    `);
    const queueLength = await redis.llen('task_queue');
    res.json({ byStatus: rows, queueLength });
  } catch (err) {
    res.status(500).json({ error: 'Failed to fetch stats' });
  }
});

// ── Start ─────────────────────────────────────────────────────────────────────
const PORT = process.env.PORT || 3000;

async function start() {
  // Retry DB connection (useful when DB container is starting up)
  for (let i = 0; i < 10; i++) {
    try {
      await initDB();
      break;
    } catch (err) {
      console.log(`DB not ready, retrying in 2s... (${i + 1}/10)`);
      await new Promise(r => setTimeout(r, 2000));
    }
  }

  app.listen(PORT, () => {
    console.log(`API listening on port ${PORT}`);
  });
}

start();
