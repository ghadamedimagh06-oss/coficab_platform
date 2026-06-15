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
const DRIVER_STATUS_STORAGE_KEY = 'coficab.driverStatuses';
const TRUCK_ASSIGNMENT_STORAGE_KEY = 'coficab.truckAssignments';

export const DRIVER_STATUS_OPTIONS = ['Active', 'En pause', 'En route'];
export const UNAVAILABLE_DRIVER_STATUSES = new Set([
  'CONGE',
  'ARRET_MALADIE',
  'INACTIF',
  'En pause',
]);

export function normalizeTruckStatus(status) {
  if (!status) return 'Available';
  const raw = String(status);
  return API_TO_TRUCK_STATUS[raw] || API_TO_TRUCK_STATUS[raw.toUpperCase()] || raw;
}

export function normalizeDriverStatus(status) {
  if (!status) return 'Active';
  const raw = String(status);
  const upper = raw.toUpperCase();
  if (upper === 'ACTIF' || raw === 'Active' || raw === 'En route') return raw === 'En route' ? 'En route' : 'Active';
  if (UNAVAILABLE_DRIVER_STATUSES.has(raw) || UNAVAILABLE_DRIVER_STATUSES.has(upper)) return 'En pause';
  return raw;
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

export function readDriverStatusOverrides() {
  if (typeof window === 'undefined') return {};
  try {
    return JSON.parse(window.localStorage.getItem(DRIVER_STATUS_STORAGE_KEY) || '{}');
  } catch {
    return {};
  }
}

export function writeDriverStatusOverride(driverId, status) {
  if (typeof window === 'undefined') return;
  const overrides = readDriverStatusOverrides();
  overrides[String(driverId)] = normalizeDriverStatus(status);
  window.localStorage.setItem(DRIVER_STATUS_STORAGE_KEY, JSON.stringify(overrides));
}

export function applyDriverStatusOverrides(drivers) {
  const overrides = readDriverStatusOverrides();
  return drivers.map((driver) => ({
    ...driver,
    status: overrides[String(driver.id)] || normalizeDriverStatus(driver.status),
  }));
}

export function readTruckAssignmentOverrides() {
  if (typeof window === 'undefined') return {};
  try {
    return JSON.parse(window.localStorage.getItem(TRUCK_ASSIGNMENT_STORAGE_KEY) || '{}');
  } catch {
    return {};
  }
}

export function writeTruckAssignmentOverride(truckId, driverId) {
  if (typeof window === 'undefined') return;
  const overrides = readTruckAssignmentOverrides();
  overrides[String(truckId)] = driverId == null || driverId === '' ? null : driverId;
  window.localStorage.setItem(TRUCK_ASSIGNMENT_STORAGE_KEY, JSON.stringify(overrides));
}

export function applyTruckAssignmentOverrides(trucks) {
  const overrides = readTruckAssignmentOverrides();
  return trucks.map((truck) => {
    const key = String(truck.id ?? truck.truck_id);
    if (!Object.prototype.hasOwnProperty.call(overrides, key)) return truck;
    const override = overrides[key];
    if (override == null || override === '') {
      return {
        ...truck,
        assigned_driver: truck.assigned_driver ?? truck.chauffeur_defaut_id ?? null,
      };
    }
    return {
      ...truck,
      assigned_driver: override,
      chauffeur_defaut_id: override,
    };
  });
}
