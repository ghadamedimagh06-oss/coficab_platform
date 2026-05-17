# CofICab Platform - Setup & Deployment Guide

## Quick Start

### Prerequisites
- **Docker** & **Docker Compose** (recommended)
- OR manually:
  - Node.js 18+
  - Python 3.9+
  - PostgreSQL 12+
  - Redis 6+

---

## Option 1: Docker Compose (Recommended)

### Step 1: Clone & Configure
```bash
git clone <repository>
cd coficab-platform

# Copy environment file
cp .env.example .env

# Create shared folder for Watchdog agent
mkdir -p shared_folder
```

### Step 2: Start All Services
```bash
docker-compose up -d
```

This will start:
- 🐘 PostgreSQL database
- 🔴 Redis cache
- 🔵 Backend API (FastAPI)
- ⚛️  Frontend (React/Next.js)
- 🤖 4 Intelligent Agents

### Step 3: Verify Services
```bash
# Check all containers
docker-compose ps

# View backend logs
docker-compose logs backend

# View specific agent logs
docker-compose logs agent1_watchdog
```

### Step 4: Access Services
- **Frontend Dashboard**: http://localhost:3000
- **Backend API**: http://localhost:8000
- **API Documentation**: http://localhost:8000/docs

---

## Option 2: Manual Setup

### 1. Database Setup

#### PostgreSQL Installation
```bash
# macOS
brew install postgresql

# Ubuntu/Debian
sudo apt-get install postgresql postgresql-contrib

# Windows: Download installer from https://www.postgresql.org/download/windows/
```

#### Create Database
```bash
psql -U postgres

# In psql terminal:
CREATE DATABASE coficab_db;
CREATE USER coficab_user WITH PASSWORD 'coficab_password';
GRANT ALL PRIVILEGES ON DATABASE coficab_db TO coficab_user;
\c coficab_db
\i database/schema.sql
\i database/seed.sql
```

### 2. Redis Setup

```bash
# macOS
brew install redis
brew services start redis

# Ubuntu/Debian
sudo apt-get install redis-server
sudo systemctl start redis-server

# Windows: https://github.com/microsoftarchive/redis/releases
```

### 3. Backend Setup

```bash
cd backend

# Create virtual environment
python -m venv venv

# Activate virtual environment
source venv/bin/activate  # macOS/Linux
# OR
venv\Scripts\activate  # Windows

# Install dependencies
pip install -r requirements.txt

# Start backend
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

Backend runs on: http://localhost:8000

### 4. Frontend Setup

```bash
cd frontend

# Install dependencies
npm install

# Start development server
npm run dev
```

Frontend runs on: http://localhost:3000

### 5. Agents Setup

#### Agent 1: Watchdog
```bash
cd agents/agent1_watchdog
pip install -r requirements.txt
python main.py
```

#### Agent 2: Scheduler
```bash
cd agents/agent2_scheduler
pip install -r requirements.txt
python main.py
```

#### Agent 3: Alert
```bash
cd agents/agent3_alert
pip install -r requirements.txt
python main.py
```

#### Agent 4: Tracker
```bash
cd agents/agent4_tracker
pip install -r requirements.txt
python main.py
```

---

## System Testing

### 1. Health Check
```bash
curl http://localhost:8000/api/health
```

### 2. Trigger Ingestion
```bash
# Place an Excel file in shared_folder
# Agent 1 (Watchdog) will detect it automatically

# Or manually trigger:
curl -X POST http://localhost:8000/api/ingestion/trigger \
  -H "Content-Type: application/json" \
  -d '{
    "file_path": "/shared_folder/plan.xlsx",
    "timestamp": 1717483800
  }'
```

### 3. Get KPI Metrics
```bash
curl http://localhost:8000/api/metrics/kpi
```

### 4. Get Live Tracking
```bash
curl http://localhost:8000/api/tracking/live
```

---

## Monitoring & Logs

### Docker Logs
```bash
# All services
docker-compose logs -f

# Specific service
docker-compose logs -f backend
docker-compose logs -f agent1_watchdog

# Last 100 lines
docker-compose logs --tail=100 backend
```

### Manual Logs
- Backend: Check terminal where `uvicorn` is running
- Agents: Check their respective terminal windows

---

## Configuration

### Environment Variables
All configuration is in `.env` file:

```bash
# Database
DATABASE_URL=postgresql://user:password@host:port/dbname

# Redis
REDIS_URL=redis://host:port

# API
BACKEND_API_URL=http://localhost:8000

# Agents
WATCH_DIRECTORY=./shared_folder
MONITOR_INTERVAL=10
POLL_INTERVAL=300
```

---

## Troubleshooting

### Port Already in Use
```bash
# Find process using port 8000
lsof -i :8000

# Kill process
kill -9 <PID>

# Or change port in .env and restart
```

### Database Connection Failed
```bash
# Check PostgreSQL is running
psql -U postgres -c "SELECT 1;"

# Check connection string in .env
# Format: postgresql://user:password@host:port/dbname
```

### Redis Connection Failed
```bash
# Check Redis is running
redis-cli ping

# Should return: PONG
```

### Frontend Blank Page
```bash
# Clear cache
rm -rf .next/ node_modules/

# Reinstall dependencies
npm install

# Restart
npm run dev
```

---

## Production Deployment

### Docker Build
```bash
docker-compose -f docker-compose.yml build
docker-compose -f docker-compose.yml up -d
```

### Cloud Deployment
- **Kubernetes**: Use provided Helm charts
- **AWS**: ECS with RDS + ElastiCache
- **Azure**: AKS with Azure Database
- **Google Cloud**: GKE with Cloud SQL

### Security Checklist
- [ ] Change default database password
- [ ] Set strong JWT_SECRET
- [ ] Enable HTTPS/SSL
- [ ] Configure firewall rules
- [ ] Set up monitoring & alerts
- [ ] Enable database backups
- [ ] Review CORS configuration

---

## Performance Tuning

### Database
```sql
-- Create indexes
CREATE INDEX idx_transports_status ON transports(status);
CREATE INDEX idx_tracking_timestamp ON tracking_history(timestamp);

-- Analyze query plans
EXPLAIN ANALYZE SELECT * FROM transports WHERE status = 'in_transit';
```

### Redis
```bash
# Monitor Redis
redis-cli MONITOR

# Check memory usage
redis-cli INFO memory

# Optimize
redis-cli CONFIG SET maxmemory 2gb
redis-cli CONFIG SET maxmemory-policy allkeys-lru
```

---

## Useful Commands

### Docker Compose
```bash
# Start services
docker-compose up -d

# Stop services
docker-compose down

# Restart service
docker-compose restart backend

# Remove volumes (careful!)
docker-compose down -v

# Scale service
docker-compose up -d --scale agent1_watchdog=2
```

### Database
```bash
# Connect to database
psql -U postgres -d coficab_db

# Backup
pg_dump -U postgres coficab_db > backup.sql

# Restore
psql -U postgres coficab_db < backup.sql
```

### Redis
```bash
# Connect to Redis
redis-cli

# Clear all data
redis-cli FLUSHALL

# View all keys
redis-cli KEYS *
```

---

## Support

For issues or questions:
1. Check documentation in `/docs`
2. Review logs in Docker or terminal
3. Check API endpoints with Swagger UI at http://localhost:8000/docs
4. Review test cases in `/tests`

---

## Next Steps

After setup:
1. ✅ Verify all services running
2. 📊 Access dashboard at http://localhost:3000
3. 🚀 Upload test Excel file to shared_folder
4. 👀 Monitor agent activities in logs
5. 📈 Check KPI metrics and tracking data
6. 🔧 Configure production settings
