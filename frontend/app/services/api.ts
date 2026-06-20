const baseURL = process.env.NEXT_PUBLIC_API_BASE_URL || process.env.NEXT_PUBLIC_API_URL || 'http://127.0.0.1:8000';
const debugAPI = process.env.NEXT_PUBLIC_DEBUG_API === 'true';

export function apiUrl(path: string) {
  if (!path) return baseURL;
  if (/^https?:\/\//i.test(path)) return path;
  return `${baseURL}${path.startsWith('/') ? path : `/${path}`}`;
}

function authHeader(): Record<string, string> {
  // Attach the JWT when one is stored (set after login). Harmless when absent:
  // protected routes fall back to the offline dev user unless REQUIRE_AUTH is on.
  if (typeof window === 'undefined') return {};
  const token = window.localStorage.getItem('access_token');
  return token ? { Authorization: `Bearer ${token}` } : {};
}

async function request(path: string, options: RequestInit = {}) {
  if (debugAPI) {
    console.log(`API Request: ${options.method || 'GET'} ${baseURL}${path}`);
  }

  const response = await fetch(`${baseURL}${path}`, {
    ...options,
    headers: {
      'Content-Type': 'application/json',
      ...authHeader(),
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

function patch(path: string, payload: any) {
  return request(path, { method: 'PATCH', body: JSON.stringify(payload) });
}

export async function getKpi() {
  return get('/api/metrics/kpi');
}

export async function getCopilotStatus() {
  return get('/api/copilot/status');
}

type CopilotMessage = { role: 'user' | 'assistant'; content: string };

/**
 * Stream a copilot reply. Calls `onToken` with each text chunk as it arrives.
 * `context` is a compact snapshot of the current screen so Claude answers
 * grounded in real data; `activity` is the page's recent-events log.
 */
export async function streamCopilotChat(
  messages: CopilotMessage[],
  {
    context,
    activity,
    onToken,
    signal,
  }: {
    context?: any;
    activity?: string[];
    onToken: (chunk: string) => void;
    signal?: AbortSignal;
  },
) {
  const response = await fetch(`${baseURL}/api/copilot/chat`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', ...authHeader() },
    body: JSON.stringify({ messages, context, activity }),
    signal,
  });

  if (!response.ok || !response.body) {
    const data = await response.json().catch(() => null);
    throw new Error(data?.detail || `Optiroute request failed (${response.status})`);
  }

  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  for (;;) {
    const { done, value } = await reader.read();
    if (done) break;
    onToken(decoder.decode(value, { stream: true }));
  }
}

export async function getSourceStatus() {
  return get('/api/data/source-status');
}

export async function getLiveTracking() {
  return get('/api/tracking/live');
}

export async function getTransports() {
  const data = await get('/api/data/transports');
  return data.transports || data;
}

export async function getDailyPlanning(day: string) {
  const data = await get(`/api/data/transports?day=${encodeURIComponent(day)}&limit=200`);
  return data.transports || data;
}

export async function getDailyPlanningFromFile() {
  const data = await get('/api/data/transports?limit=1000');
  return data.transports || data;
}

export async function getDailyPlanningFileResponse() {
  return get('/api/data/transports?limit=1000');
}

export async function getFleetTrucks() {
  return get('/api/fleet/trucks');
}

export async function getFleetDrivers() {
  return get('/api/fleet/drivers');
}

export async function updateTruckStatus(truckId: number | string, status: string) {
  return patch(`/api/fleet/trucks/${truckId}/status`, { status });
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

export async function generateDailyPlan(day: string, sourceFile?: string, trucks?: any[]) {
  return post('/api/planning/daily/generate', {
    day,
    source_file: sourceFile,
    trucks,
  });
}

export async function getDailyPareto(day: string, objectives?: string[], trucks?: any[]) {
  return post('/api/planning/daily/pareto', {
    day,
    objectives: objectives && objectives.length ? objectives : ['green', 'balanced', 'fast'],
    trucks,
  });
}

export async function getEsgReport(day: string, objective: string = 'balanced') {
  return get(`/api/planning/daily/esg-report?day=${encodeURIComponent(day)}&objective=${encodeURIComponent(objective)}`);
}

export async function explainTruck(plan: any, truckId: number | string) {
  return post('/api/planning/daily/explain', { plan, truck_id: truckId });
}

export async function replanPlan(
  day: string,
  { plan, disruptedTruckIds, completedStopIds, objective }:
    { plan: any; disruptedTruckIds?: (number | string)[]; completedStopIds?: any[]; objective?: string },
) {
  return post('/api/planning/daily/replan', {
    day,
    plan,
    disrupted_truck_ids: disruptedTruckIds || [],
    completed_stop_ids: completedStopIds || [],
    objective: objective || 'balanced',
  });
}

export async function getPlanConfidence(
  day: string,
  { plan, trucks, objective, runs }: { plan?: any; trucks?: any[]; objective?: string; runs?: number } = {},
) {
  return post('/api/planning/daily/confidence', {
    day,
    plan,
    trucks,
    objective: objective || 'balanced',
    runs: runs || 500,
  });
}

export async function runStressTest(
  day: string,
  { trucks, objective, scenarios }: { trucks?: any[]; objective?: string; scenarios?: any[] } = {},
) {
  return post('/api/planning/daily/stress-test', {
    day,
    trucks,
    objective: objective || 'balanced',
    scenarios: scenarios || [],
  });
}

export async function copilotAction(
  text: string,
  { plan, day, objective }: { plan?: any; day?: string; objective?: string } = {},
) {
  return post('/api/copilot/action', {
    text,
    plan,
    day: day || (plan && plan.day),
    objective: objective || (plan && plan.objective) || 'balanced',
  });
}

export async function getControlTower(
  day: string,
  { plan, asOf, delays, objective }:
    { plan?: any; asOf?: string; delays?: any; objective?: string } = {},
) {
  return post('/api/planning/daily/control-tower', {
    day,
    plan,
    as_of: asOf,
    delays: delays || [],
    objective: objective || 'balanced',
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
