import useSWR from "swr";
import { fetcher } from "@/lib/api";

export type DashKpi = { id: string; label: string; value: number; unit: string; icon: string };
export type FleetRow = { name: string; type: string; utilization: number; trips: number; positions: number; capacity: number };
export type EffSeg = { name: string; value: number; color: string; count: number };
export type ActivityRow = { id: string; route: string; description: string; time: string; status: string };
export type AlertRow = { id: string; severity: string; title: string; description: string; icon: string };
export type WeekRow = { day: string; date: string; delivered: number; planned: number; trucks: number };

export type DashPeriod = "daily" | "weekly" | "monthly";

export type KpiPeriod = { period: DashPeriod; label: string; month: string; range: string; days: number };

export type DailyDashboard = {
  day: string;
  period: DashPeriod;
  generated_at: string | null;
  source_file: string | null;
  kpis: DashKpi[];
  kpi_period: KpiPeriod;
  fleet: FleetRow[];
  efficiency: EffSeg[];
  efficiency_score: number;
  activity: ActivityRow[];
  alerts: AlertRow[];
  weekly: WeekRow[];
  totals: {
    deliveries: number;
    positions_planned: number;
    positions_unassigned: number;
    active_trucks: number;
    avg_utilization: number;
    distance_km: number;
    co2_kg: number;
    fuel_l: number;
  };
};

export function useDailyDashboard(day?: string, period: DashPeriod = "weekly", trucks?: any[]) {
  const params = new URLSearchParams();
  if (day) params.set("day", day);
  if (period) params.set("period", period);
  // Send the active fleet (trucks not marked unavailable) so the dashboard plans
  // with the same trucks as the planning screen and agrees on what's unassigned.
  if (trucks && trucks.length) params.set("trucks", JSON.stringify(trucks));
  const qs = params.toString();
  const { data, error, isLoading, mutate } = useSWR<DailyDashboard>(
    `/api/planning/daily/dashboard${qs ? `?${qs}` : ""}`,
    fetcher,
    { refreshInterval: 180_000, revalidateOnFocus: false, keepPreviousData: true }
  );
  return { dashboard: data, error, isLoading, mutate };
}
