# Technical Requirements

## Project Overview
CofICab Platform is a multi-agent intelligent logistics platform designed to automate planning, monitor operations in real-time, and reduce manual errors.

---

## Functional Requirements

### FR1: Real-Time File Monitoring
- System must detect new Excel files in shared folder within 1 second
- Support for .xlsx and .xls formats
- Automatic triggering of ingestion pipeline

### FR2: Automated Planning
- Daily planning execution with time < 3 minutes
- Data processing within 1 second detection latency
- Batch processing support

### FR3: Real-Time Tracking
- Poll TFM system every 5 minutes
- Calculate ETA based on distance and speed
- Update tracking dashboard in real-time

### FR4: Alert Management
- Monitor KPI thresholds:
  - Planning time < 180 seconds
  - Detection latency < 30 seconds
  - Data error rate < 1%
- Generate alerts with severity levels (info, warning, critical)
- Store alerts in Redis for fast retrieval

### FR5: Dashboard
- Display live tracking data
- Show KPI metrics
- Real-time alerts notification
- User authentication (JWT)

---

## Non-Functional Requirements

### Performance
- Response time: < 500ms for API endpoints
- Ingestion pipeline: < 3 minutes for full plan processing
- Real-time tracking latency: < 30 seconds
- System uptime: 99.5%

### Scalability
- Support for 500+ concurrent transports
- Handle 1000+ API requests/minute
- Database optimization for large datasets

### Security
- JWT authentication for all protected endpoints
- CORS enabled for frontend communication
- Password hashing and secure storage
- API rate limiting

### Reliability
- Database transactions with rollback support
- Error logging and monitoring
- Backup and recovery procedures
- Agent health monitoring

---

## Technical Stack

### Frontend
- React 18+
- Next.js 13+
- TypeScript
- Tailwind CSS
- Axios for API calls

### Backend
- Python 3.9+
- FastAPI framework
- SQLAlchemy ORM
- PostgreSQL 12+
- Redis 6+

### Multi-Agent System
- Python 3.9+
- watchdog (file monitoring)
- APScheduler (task scheduling)
- requests (HTTP communication)
- redis-py (Redis client)

### Infrastructure
- Docker & Docker Compose
- PostgreSQL database
- Redis cache
- Nginx reverse proxy

---

## Database Schema Requirements

### Core Tables
1. **transports** - Transport records
2. **drivers** - Driver information
3. **vehicles** - Vehicle fleet data
4. **routes** - Route definitions
5. **tracking_history** - Historical tracking data
6. **alerts** - System alerts log
7. **users** - User authentication

### Key Indexes
- `transports(status)` - For status queries
- `tracking_history(transport_id, timestamp)` - For time-series queries
- `alerts(severity, created_at)` - For alert filtering

---

## API Endpoints Summary

| Method | Endpoint | Purpose |
|--------|----------|---------|
| POST | /api/ingestion/trigger | Trigger ingestion |
| POST | /api/optimization/route | Optimize route |
| GET | /api/data/transports | Get transports |
| POST | /api/data/transports | Create transport |
| POST | /api/tasks/daily-planning | Run planning |
| POST | /api/tasks/process-data | Process data |
| POST | /api/auth/login | User login |
| GET | /api/metrics/kpi | Get KPI metrics |
| POST | /api/tracking/sync | Sync tracking |
| GET | /api/tracking/live | Get live data |

---

## Agent Communication Flow

```
User uploads Excel
       ↓
Agent 1 (Watchdog) detects file
       ↓
Calls: POST /api/ingestion/trigger
       ↓
Backend processes data
       ↓
Agent 2 (Scheduler) runs daily tasks
       ↓
Calls: POST /api/tasks/daily-planning
       ↓
Backend completes planning
       ↓
Agent 4 (Tracker) polls TFM system every 5 min
       ↓
Calls: POST /api/tracking/sync
       ↓
Agent 3 (Alert) monitors KPIs
       ↓
Calls: GET /api/metrics/kpi
       ↓
If threshold exceeded: POST /api/alerts
       ↓
Dashboard shows live data
```

---

## Expected Improvements

| Metric | Before | After | Improvement |
|--------|--------|-------|-------------|
| Planning Time | 15-21 min | < 3 min | 7-5x faster |
| Detection Latency | ~4 hours | < 30 sec | 480x faster |
| Data Errors | 12-18% | ~0% | Near-zero |
| Manual Work | 100% | 10% | 90% automation |
| Operational Cost | 100% | 40% | 60% savings |

---

## Deployment Checklist

- [ ] PostgreSQL installed and configured
- [ ] Redis server running
- [ ] Frontend build artifacts ready
- [ ] Backend requirements installed
- [ ] Agents dependencies installed
- [ ] Environment variables configured
- [ ] Database migrations executed
- [ ] API endpoints tested
- [ ] SSL/TLS certificates configured
- [ ] Monitoring and logging setup
- [ ] Backup procedures documented
- [ ] Disaster recovery plan ready

---

## Support & Maintenance

### Monitoring
- System health checks every 5 minutes
- Log aggregation with ELK stack
- Performance metrics with Prometheus
- Alerts with PagerDuty

### Backup Strategy
- Daily database backups
- Weekly full system backup
- Monthly off-site archive
- Recovery RTO: 4 hours, RPO: 1 hour

### Version Control
- Git-based deployment
- Semantic versioning (semver)
- Automated CI/CD pipeline
- Staging and production environments
