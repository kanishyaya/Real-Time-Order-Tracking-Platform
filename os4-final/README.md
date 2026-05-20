# OrderStream — Real-Time Order Tracking

A full-stack event-driven system where every change to an order is instantly
broadcast to **all connected portals** without polling or page refreshes.
Open three browser tabs on different ports — create an order on one and watch
it appear on the others in under a second.

---

## Architecture

```
Browser Tab          Browser Tab          Browser Tab
(localhost:4000)     (localhost:4001)     (localhost:4002)
      |                    |                    |
   nginx               nginx               nginx
      |                    |                    |
      +--------------------+--------------------+
                           |
                    FastAPI Backend
                    (single process)
                           |
              +------------+------------+
              |                         |
        asyncpg pool             ConnectionManager
        (REST API)               (WebSocket registry)
              |                         ^
              |                         |
        PostgreSQL               Redis Broadcaster
        orders table             (subscribes to Redis)
              |                         |
        DB Trigger               Redis Pub/Sub
        (NOTIFY on every         (order_updates channel)
         INSERT/UPDATE/DELETE)         |
              |                         |
              +-------- DB Listener ----+
                        (asyncpg LISTEN)
```

### Event flow — step by step

1. User creates / updates / deletes an order via the REST API
2. PostgreSQL trigger fires `NOTIFY order_updates` with a JSON payload
3. DB Listener (asyncpg) receives the notification and publishes it to Redis
4. Redis Broadcaster (separate connection) receives from Pub/Sub
5. `ConnectionManager.broadcast()` fans the message out to **every** connected
   WebSocket client across all portals simultaneously
6. Each browser tab receives the event and patches its local state — no refresh

---

## Tech Stack

| Layer      | Technology                        |
|------------|-----------------------------------|
| Frontend   | React 18, Vite, nginx             |
| Backend    | Python 3.11, FastAPI, uvicorn     |
| Database   | PostgreSQL 16                     |
| Pub/Sub    | Redis 7                           |
| Auth       | JWT (python-jose)                 |
| Container  | Docker, Docker Compose            |

---

## Folder Structure

```
os4-final/
├── docker-compose.yml          # Spins up all services + 3 portals
│
├── sql/
│   ├── schema.sql              # orders + order_events tables
│   ├── triggers.sql            # notify_order_change() trigger
│   └── seed.sql                # Optional sample data
│
├── backend/
│   ├── main.py                 # FastAPI app, lifespan, WebSocket endpoint
│   ├── config.py               # All env vars in one place
│   ├── database.py             # asyncpg pool, schema init, event fetch
│   ├── models.py               # Pydantic request/response models
│   ├── auth.py                 # JWT create / verify
│   ├── routes_orders.py        # REST CRUD endpoints
│   ├── websocket_manager.py    # ConnectionManager — tracks all WS clients
│   ├── db_listener.py          # asyncpg LISTEN → Redis PUBLISH
│   ├── redis_broadcaster.py    # Redis SUBSCRIBE → WebSocket broadcast
│   ├── redis_pubsub.py         # Thin Redis client helpers
│   ├── requirements.txt
│   └── Dockerfile
│
└── frontend/
    ├── src/
    │   ├── components/
    │   │   ├── Dashboard.jsx       # Main view — orders grid + event log
    │   │   ├── OrderCard.jsx       # Individual order card with actions
    │   │   ├── CreateOrderModal.jsx
    │   │   ├── EventLog.jsx        # Real-time sidebar event feed
    │   │   ├── MetricsBar.jsx      # Live connected clients + uptime
    │   │   ├── ConnectionBadge.jsx # WebSocket status indicator
    │   │   └── LoginPage.jsx
    │   ├── hooks/
    │   │   ├── useWebSocket.js     # WS connect / reconnect / broadcast
    │   │   └── AuthContext.jsx     # JWT storage + login/logout
    │   └── utils/
    │       └── api.js              # All fetch() calls to the REST API
    ├── nginx.conf                  # Proxies /api/* and /ws to backend
    ├── vite.config.js
    ├── package.json
    └── Dockerfile
```

---

## Setup & Running

### Prerequisites

- [Docker Desktop](https://www.docker.com/products/docker-desktop/) installed and running
- Ports `4000`, `4001`, `4002` free on your machine

### 1 — Clone / unzip the project

```bash
# If you have the zip
unzip os4-final.zip
cd os4-final
```

### 2 — Start everything

```bash
docker compose up --build
```

### 3 — Wait for these lines in the terminal

```
redis-1     | Ready to accept connections
backend-1   | Schema and triggers applied.
backend-1   | Application startup complete.
frontend-1  | start worker process
```

### 4 — Open the portals

| Portal   | URL                      | Login               |
|----------|--------------------------|---------------------|
| Portal 1 | http://localhost:4000    | admin / admin123    |
| Portal 2 | http://localhost:4001    | viewer / viewer123  |
| Portal 3 | http://localhost:4002    | admin / admin123    |

### 5 — Verify real-time sync

1. Open all three URLs in separate browser tabs
2. Create an order on `:4000`
3. It appears instantly on `:4001` and `:4002` — no refresh needed
4. Change a status on `:4001` — both other tabs update immediately
5. The **event log sidebar** on the right shows every change live

---

## Docker Commands

```bash
# Start all services (first run — builds images)
docker compose up --build

# Start in background
docker compose up --build -d

# View live logs
docker compose logs -f

# View backend logs only
docker compose logs backend -f

# Stop everything (keeps database data)
docker compose down

# Stop and wipe the database (full reset)
docker compose down -v

# Rebuild after code changes
docker compose down -v
docker rmi os4-final-frontend os4-final-frontend2 os4-final-frontend3 os4-final-backend --force
docker compose up --build

# Open a shell inside the backend container
docker compose exec backend bash

# Connect to PostgreSQL directly
docker compose exec db psql -U postgres -d orders_db
```

---

## API Endpoints

Base URL: `http://localhost:4000/api`

Interactive docs: `http://localhost:4000/api/docs`

### Auth

| Method | Endpoint         | Description              | Auth required |
|--------|------------------|--------------------------|---------------|
| POST   | `/auth/login`    | Get a JWT token          | No            |

**Request body:**
```json
{ "username": "admin", "password": "admin123" }
```

**Response:**
```json
{ "access_token": "eyJhbGci..." }
```

### Orders

All order endpoints require `Authorization: Bearer <token>` header.

| Method | Endpoint           | Description         | Status code |
|--------|--------------------|---------------------|-------------|
| GET    | `/orders`          | List all orders     | 200         |
| POST   | `/orders`          | Create an order     | 201         |
| PUT    | `/orders/{id}`     | Update an order     | 200         |
| DELETE | `/orders/{id}`     | Delete an order     | 204         |

**Create order — request body:**
```json
{
  "customer_name": "Alice Johnson",
  "product_name":  "Wireless Headphones",
  "status":        "pending"
}
```

**Order response:**
```json
{
  "id":            1,
  "customer_name": "Alice Johnson",
  "product_name":  "Wireless Headphones",
  "status":        "pending",
  "updated_at":    "2024-01-15 10:30:00"
}
```

**Update order — request body (all fields optional):**
```json
{ "status": "shipped" }
```

**Status values:** `pending` → `shipped` → `delivered`

### System

| Method | Endpoint    | Description                        | Auth required |
|--------|-------------|------------------------------------|---------------|
| GET    | `/health`   | Database + Redis health check      | No            |
| GET    | `/metrics`  | Connected clients, uptime, events  | Yes           |

**Metrics response:**
```json
{
  "connected_clients":  3,
  "total_events_fired": 42,
  "uptime_seconds":     3600.5
}
```

---

## WebSocket Usage

### Connect

```
ws://localhost:4000/ws?token=<JWT>
ws://localhost:4001/ws?token=<JWT>
ws://localhost:4002/ws?token=<JWT>
```

All three connect to the **same backend** — so all clients on all ports
receive every broadcast.

### Message types

**On connect — server sends a confirmation:**
```json
{
  "type":      "connection",
  "message":   "Connected to real-time order updates.",
  "client_id": "7e21124a-..."
}
```

**On connect — server replays the last 50 events:**
```json
{
  "type":   "replay",
  "events": [ ... ],
  "count":  12
}
```

**On any order change — server broadcasts to all clients:**
```json
{
  "operation": "INSERT",
  "table":     "orders",
  "data": {
    "id":            3,
    "customer_name": "Bob Smith",
    "product_name":  "Laptop Stand",
    "status":        "pending",
    "updated_at":    "2024-01-15 10:30:00"
  },
  "timestamp": 1705312200.123
}
```

`operation` is one of: `INSERT`, `UPDATE`, `DELETE`

### JavaScript example

```javascript
const token = 'eyJhbGci...'
const ws = new WebSocket(`ws://localhost:4000/ws?token=${token}`)

ws.onopen = () => console.log('Connected')

ws.onmessage = (evt) => {
  const msg = JSON.parse(evt.data)

  if (msg.type === 'connection') return
  if (msg.type === 'replay') {
    console.log(`Caught up with ${msg.count} past events`)
    return
  }

  const { operation, data } = msg
  console.log(`${operation} — order #${data.id} (${data.status})`)
}

ws.onclose = () => console.log('Disconnected')
```

---

## Scalability

### How it scales horizontally

The architecture uses **Redis Pub/Sub as the message bus** between backend
instances. This means you can run multiple backend replicas behind a load
balancer and all connected clients still receive every event:

```
Load Balancer
    |
    +--------+--------+
    |                 |
Backend 1         Backend 2
(clients A, B)    (clients C, D)
    |                 |
    +----> Redis <----+
           (shared Pub/Sub channel)
```

When an order changes, the DB trigger fires once. Redis fans it out to every
backend instance. Each instance broadcasts to its own pool of WebSocket
clients. All clients on all instances receive the event.

### Scaling checklist

| Concern              | Solution                                              |
|----------------------|-------------------------------------------------------|
| More portals         | Add `frontendN` services in `docker-compose.yml`      |
| More backend workers | Add replicas behind nginx upstream load balancing     |
| Database load        | Add read replicas; write path stays on primary        |
| Redis reliability    | Switch to Redis Sentinel or Redis Cluster             |
| Auth in production   | Replace demo passwords with a real user store + bcrypt|
| HTTPS / WSS          | Add SSL termination at the nginx or load balancer layer|

### Why not polling?

Polling (fetching `/orders` every N seconds) wastes bandwidth, adds latency,
and hammers the database proportionally to the number of clients. With this
architecture, a single DB write triggers exactly one `NOTIFY`, one Redis
publish, and one fan-out — regardless of how many clients are connected.
Cost is O(1) per event, not O(clients × poll_interval).

---

## Demo Credentials

| Username | Password   | Role   | Can create/edit/delete |
|----------|------------|--------|------------------------|
| admin    | admin123   | admin  | Yes                    |
| viewer   | viewer123  | viewer | Yes (demo mode)        |

---

## Environment Variables

Configured in `docker-compose.yml` under the `backend` service:

| Variable             | Default                                        | Description                  |
|----------------------|------------------------------------------------|------------------------------|
| `DATABASE_URL`       | `postgresql://postgres:password@db:5432/...`   | PostgreSQL connection string  |
| `REDIS_URL`          | `redis://redis:6379`                           | Redis connection string       |
| `JWT_SECRET`         | `orderstream-secret-key-2024`                  | Change this in production     |
| `JWT_EXPIRY_MINUTES` | `60`                                           | Token lifetime in minutes     |
| `CORS_ORIGINS`       | `http://localhost:4000,...`                    | Comma-separated allowed origins|
| `APP_ENV`            | `production`                                   | `development` or `production` |
