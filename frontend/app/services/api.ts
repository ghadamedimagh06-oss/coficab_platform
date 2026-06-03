const baseURL = process.env.NEXT_PUBLIC_API_BASE_URL || process.env.NEXT_PUBLIC_API_URL || 'http://127.0.0.1:8000';
const debugAPI = process.env.NEXT_PUBLIC_DEBUG_API === 'true';

export function apiUrl(path: string) {
  if (!path) return baseURL;
  if (/^https?:\/\//i.test(path)) return path;
  return `${baseURL}${path.startsWith('/') ? path : `/${path}`}`;
}

async function request(path: string, options: RequestInit = {}) {
  if (debugAPI) {
    console.log(`API Request: ${options.method || 'GET'} ${baseURL}${path}`);
  }

  const response = await fetch(`${baseURL}${path}`, {
    ...options,
    headers: {
      'Content-Type': 'application/json',
      ...(options.headers || {}),
    },
  });
  const data = await response.json().catch(() => null);

  if (!response.ok) {
    const error: any = new Error(data?.detail || response.statusText);
    error.response = { status: response.status, data };
    throw error;
  }

  if (debugAPI) {
    console.log(`API Response: ${response.status} ${path}`, data);
  }
  return data;
}

function get(path: string) {
  return request(path);
}

function post(path: string, payload: any) {
  return request(path, { method: 'POST', body: JSON.stringify(payload) });
}

function put(path: string, payload: any) {
  return request(path, { method: 'PUT', body: JSON.stringify(payload) });
}

export async function getKpi() {
  return get('/api/metrics/kpi');
}

export async function getLiveTracking() {
  return get('/api/tracking/live');
}

export async function getTransports() {
  const data = await get('/api/data/transports');
  return data.transports || data;
}

export async function getDailyPlanning(day: string) {
  const data = await get(`/api/data/transports?day=${encodeURIComponent(day)}&limit=200&force_file=true`);
  return data.transports || data;
}

export async function getDailyPlanningFromFile() {
  const data = await get('/api/data/transports?limit=1000&force_file=true');
  return data.transports || data;
}

export async function getDailyPlanningFileResponse() {
  return get('/api/data/transports?limit=1000&force_file=true');
}

export async function getAgentStatus() {
  return get('/api/agents/status');
}

export async function generateOptimizationPlanning(payload: any = { deliveries: [], trucks: [], current_routes: [] }) {
  return post('/api/optimization/planning/generate', payload);
}

export async function proposeOptimization(payload: any) {
  return post('/api/optimization/route', payload);
}

export async function generatePlanning(payload: any) {
  return post('/api/optimization/planning/generate', payload);
}

export async function generateDailyPlan(day: string, sourceFile?: string) {
  return post('/api/planning/daily/generate', {
    day,
    source_file: sourceFile,
  });
}

export async function exportDailyPlan(payload: any) {
  const result = await post('/api/planning/daily/export', payload);
  return {
    ...result,
    download_url: result?.download_url ? apiUrl(result.download_url) : result?.download_url,
  };
}

export async function triggerIngestion(filePath: string) {
  return post('/api/ingestion/trigger', {
    file_path: filePath,
    timestamp: Date.now(),
  });
}

export async function syncDailyPlanning() {
  return post('/api/tasks/daily-planning', {});
}

export async function processDataTask() {
  return post('/api/tasks/process-data', {});
}

export async function getImpactPreview(planningId, field, newValue) {
  return get(`/api/planning/${planningId}/impact-preview?field=${encodeURIComponent(field)}&new_value=${encodeURIComponent(newValue)}`);
}

export async function validatePlanning(planningId, userId) {
  return post('/api/planning/validate', {
    planning_id: planningId,
    user_id: userId,
  });
}

export async function updatePlanning(payload) {
  return put('/api/planning/update', payload);
}
