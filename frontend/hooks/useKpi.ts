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

export function useKpi() {
  const { data, error, isLoading, mutate } = useSWR<{ kpis: Kpi[] }>(
    "/api/metrics/kpi",
    fetcher,
    { refreshInterval: 60_000 }
  );
  return { kpis: data?.kpis ?? [], error, isLoading, mutate };
}
