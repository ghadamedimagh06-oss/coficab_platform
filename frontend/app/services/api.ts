import axios from 'axios';

const baseURL = process.env.NEXT_PUBLIC_API_BASE_URL || 'http://localhost:8001';
const debugAPI = process.env.NEXT_PUBLIC_DEBUG_API === 'true';

const api = axios.create({
  baseURL,
  headers: {
    'Content-Type': 'application/json',
  },
});

// Add request interceptor for debugging
api.interceptors.request.use(
  (config) => {
    if (debugAPI) {
      console.log(`🔵 API Request: ${config.method?.toUpperCase()} ${baseURL}${config.url}`);
    }
    return config;
  },
  (error) => {
    console.error('❌ API Request Error:', error);
    return Promise.reject(error);
  }
);

// Add response interceptor for debugging
api.interceptors.response.use(
  (response) => {
    if (debugAPI) {
      console.log(`✅ API Response: ${response.status} ${response.config.url}`, response.data);
    }
    return response;
  },
  (error) => {
    if (debugAPI) {
      console.error(`❌ API Error: ${error.response?.status || 'No response'} ${error.config?.url}`, error.message);
    }
    return Promise.reject(error);
  }
);

export async function getKpi() {
  const response = await api.get('/api/metrics/kpi');
  return response.data;
}

export async function getLiveTracking() {
  const response = await api.get('/api/tracking/live');
  return response.data;
}

export async function getTransports() {
  const response = await api.get('/api/data/transports');
  return response.data.transports || response.data;
}

export async function proposeOptimization(payload: any) {
  const response = await api.post('/api/optimization/route', payload);
  return response.data;
}

export async function triggerIngestion(filePath: string) {
  const response = await api.post('/api/ingestion/trigger', {
    file_path: filePath,
    timestamp: Date.now(),
  });
  return response.data;
}

export async function syncDailyPlanning() {
  const response = await api.post('/api/tasks/daily-planning', {});
  return response.data;
}

export async function processDataTask() {
  const response = await api.post('/api/tasks/process-data', {});
  return response.data;
}

export async function getImpactPreview(planningId, field, newValue) {
  const response = await api.get(`/api/planning/${planningId}/impact-preview`, {
    params: { field, new_value: newValue },
  });
  return response.data;
}

export async function validatePlanning(planningId, userId) {
  const response = await api.post('/api/planning/validate', {
    planning_id: planningId,
    user_id: userId,
  });
  return response.data;
}

export async function updatePlanning(payload) {
  const response = await api.put('/api/planning/update', payload);
  return response.data;
}
