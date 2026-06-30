import useSWR from "swr";
import { fetcher } from "@/lib/api";

export type Kpi = {
  code: string;
  label: string;
  value: number | null;
  unit: string;
  color: "green" | "yellow" | "red" | "grey";
  target: number | null;
  trend: number | null;
};

export type OperationalSummary = {
  distance_travelled_km?: number;
  fuel_consumed_l?: number;
  tonne_km?: number;
  fuel_l_per_100km?: number | null;
};

export function useKpi(period: "day" | "week" | "month" | "year" = "month") {
  const { data, error, isLoading, mutate } = useSWR<{
    kpis: Kpi[];
    operational: OperationalSummary;
  }>(
    `/api/metrics/kpi?period=${period}`,
    fetcher,
    { refreshInterval: 60_000 }
  );
  return {
    kpis: data?.kpis ?? [],
    operational: data?.operational ?? {},
    error,
    isLoading,
    mutate,
  };
}
