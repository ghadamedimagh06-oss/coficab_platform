export const TRUCK_STATUS_OPTIONS = ['Available', 'In transit', 'Broken down', 'Maintenance'];

export const API_TO_TRUCK_STATUS = {
  DISPONIBLE: 'Available',
  EN_MISSION: 'In transit',
  PANNE: 'Broken down',
  MAINTENANCE: 'Maintenance',
  Disponible: 'Available',
  'En route': 'In transit',
  'En panne': 'Broken down',
  'En maintenance': 'Maintenance',
};

export const TRUCK_STATUS_TO_API = {
  Available: 'DISPONIBLE',
  'In transit': 'EN_MISSION',
  'Broken down': 'PANNE',
  Maintenance: 'MAINTENANCE',
};

export const TRUCK_STATUS_STYLES = {
  Available: 'bg-[#ecfdf5] text-[#15803d]',
  'In transit': 'bg-[#eff6ff] text-[#2563eb]',
  'Broken down': 'bg-[#fee2e2] text-[#dc2626]',
  Maintenance: 'bg-[#fef3c7] text-[#b45309]',
};

export const UNAVAILABLE_TRUCK_STATUSES = new Set([
  'PANNE',
  'MAINTENANCE',
  'Broken down',
  'Maintenance',
  'En panne',
  'En maintenance',
]);

const STORAGE_KEY = 'coficab.truckStatuses';

export function normalizeTruckStatus(status) {
  if (!status) return 'Available';
  const raw = String(status);
  return API_TO_TRUCK_STATUS[raw] || API_TO_TRUCK_STATUS[raw.toUpperCase()] || raw;
}

export function canSyncTruckStatus(truckId) {
  return Number.isInteger(Number(truckId)) && Number(truckId) > 0;
}

export function readTruckStatusOverrides() {
  if (typeof window === 'undefined') return {};
  try {
    return JSON.parse(window.localStorage.getItem(STORAGE_KEY) || '{}');
  } catch {
    return {};
  }
}

export function writeTruckStatusOverride(truckId, status) {
  if (typeof window === 'undefined') return;
  const overrides = readTruckStatusOverrides();
  overrides[String(truckId)] = normalizeTruckStatus(status);
  window.localStorage.setItem(STORAGE_KEY, JSON.stringify(overrides));
}

export function applyTruckStatusOverrides(trucks) {
  const overrides = readTruckStatusOverrides();
  return trucks.map((truck) => ({
    ...truck,
    status: overrides[String(truck.id)] || normalizeTruckStatus(truck.status),
  }));
}
