import useSWR from "swr";
import { fetcher } from "@/lib/api";

export type Truck = {
  id: number;
  plate_number: string;
  type: string;
  capacite_kg: number | null;
  max_palettes: number;
  status: string;
  chauffeur_defaut_id: number | null;
};

export type Driver = {
  id: number;
  full_name: string;
  phone: string | null;
  permis_type: string;
  status: string;
  camion_defaut_id: number | null;
  shift_start: string | null;
  shift_end: string | null;
};

export type FleetUtilization = {
  total: number;
  by_status: Record<string, number>;
  utilization_pct: number;
};

export function useFleet() {
  const { data: trucks, error: trucksError, isLoading: trucksLoading, mutate } = useSWR<Truck[]>(
    "/api/fleet/trucks",
    fetcher,
    { refreshInterval: 120_000 }
  );
  const { data: utilization, error: utilError } = useSWR<FleetUtilization>(
    "/api/fleet/utilization",
    fetcher,
    { refreshInterval: 120_000 }
  );
  return {
    trucks: trucks ?? [],
    utilization,
    error: trucksError ?? utilError,
    isLoading: trucksLoading,
    mutate,
  };
}

export function useDrivers() {
  const { data, error, isLoading } = useSWR<Driver[]>(
    "/api/fleet/drivers",
    fetcher,
    { refreshInterval: 300_000 }
  );
  return { drivers: data ?? [], error, isLoading };
}
