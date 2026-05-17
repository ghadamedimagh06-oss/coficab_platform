# API Specification

## Base URL
```
http://localhost:8000
```

## Authentication
JWT Bearer token in Authorization header:
```
Authorization: Bearer {access_token}
```

---

## Endpoints

### Health & Status

#### GET /
Root endpoint
```json
{
  "message": "CofICab Platform API",
  "status": "active",
  "timestamp": "2026-05-04T10:30:00"
}
```

#### GET /api/health
System health check
```json
{
  "status": "healthy",
  "timestamp": "2026-05-04T10:30:00"
}
```

---

## Layer 1: Ingestion

#### POST /api/ingestion/trigger
Trigger data ingestion pipeline

**Request Body**:
```json
{
  "file_path": "/shared_folder/plan_2026_05.xlsx",
  "timestamp": 1717483800
}
```

**Response**:
```json
{
  "status": "ingestion_started",
  "file_path": "/shared_folder/plan_2026_05.xlsx",
  "timestamp": "2026-05-04T10:30:00"
}
```

---

## Layer 2: Optimization & AI

#### POST /api/optimization/route
Optimize route using OR-Tools

**Request Body**:
```json
{
  "waypoints": [
    {"lat": 48.8566, "lng": 2.3522},
    {"lat": 48.8946, "lng": 2.3361}
  ],
  "constraints": {
    "max_distance": 100,
    "time_window": [8, 18]
  }
}
```

**Response**:
```json
{
  "status": "optimized",
  "original_distance": 1000,
  "optimized_distance": 850,
  "savings_percent": 15
}
```

---

## Layer 3: Storage & Data

#### GET /api/data/transports
Retrieve all transports

**Query Parameters**:
- `status` (optional): Filter by status
- `limit` (optional): Limit results (default: 100)
- `offset` (optional): Pagination offset

**Response**:
```json
{
  "transports": [
    {
      "id": "transport_001",
      "driver": "Jean Dupont",
      "vehicle": "VAN-123",
      "status": "in_transit",
      "start_location": "Paris",
      "end_location": "Lyon",
      "created_at": "2026-05-04T08:00:00"
    }
  ],
  "total": 150
}
```

#### POST /api/data/transports
Create new transport record

**Request Body**:
```json
{
  "driver": "Marie Martin",
  "vehicle": "TRUCK-456",
  "start_location": "Paris",
  "end_location": "Marseille",
  "distance_km": 660
}
```

**Response**:
```json
{
  "id": "transport_001",
  "status": "created",
  "timestamp": "2026-05-04T10:30:00"
}
```

---

## Layer 4: Backend API

#### POST /api/tasks/daily-planning
Execute daily planning task

**Response**:
```json
{
  "status": "completed",
  "planning_time": 120,
  "records_processed": 150,
  "timestamp": "2026-05-04T10:30:00"
}
```

#### POST /api/tasks/process-data
Process ingested data

**Response**:
```json
{
  "status": "completed",
  "records_processed": 150,
  "timestamp": "2026-05-04T10:30:00"
}
```

#### POST /api/auth/login
User authentication

**Request Body**:
```json
{
  "username": "admin",
  "password": "password123"
}
```

**Response**:
```json
{
  "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
  "token_type": "bearer",
  "expires_in": 3600
}
```

---

## Layer 5: Interfaces (Tracking & Metrics)

#### GET /api/metrics/kpi
Get current KPI metrics

**Response**:
```json
{
  "planning_time": 120,
  "detection_latency": 15,
  "data_error_rate": 0.005
}
```

#### POST /api/tracking/sync
Sync real-time tracking data

**Request Body**:
```json
{
  "transport_001": {
    "transport_id": "transport_001",
    "status": "in_transit",
    "location": {"lat": 48.8566, "lng": 2.3522},
    "eta_hours": 2.5,
    "distance_remaining": 200,
    "timestamp": "2026-05-04T10:30:00"
  }
}
```

**Response**:
```json
{
  "status": "synced",
  "count": 25,
  "timestamp": "2026-05-04T10:30:00"
}
```

#### GET /api/tracking/live
Get live tracking dashboard data

**Response**:
```json
{
  "tracking_data": {
    "transport_001": {
      "transport_id": "transport_001",
      "status": "in_transit",
      "location": {"lat": 48.8566, "lng": 2.3522},
      "eta_hours": 2.5,
      "distance_remaining": 200
    }
  },
  "count": 25,
  "timestamp": "2026-05-04T10:30:00"
}
```

---

## Error Responses

### 400 Bad Request
```json
{
  "detail": "Invalid request parameters"
}
```

### 401 Unauthorized
```json
{
  "detail": "Not authenticated"
}
```

### 500 Internal Server Error
```json
{
  "detail": "Internal server error"
}
```
