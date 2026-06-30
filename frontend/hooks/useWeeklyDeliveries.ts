import useSWR from "swr";
import { fetcher } from "@/lib/api";

export type WeekRow = {
  week: string;
  label: string;
  period: string;
  iso_year: number;
  iso_week: number;
  date: string;
  total: number;
  delivered: number;
  on_time: number;
};

export function useWeeklyDeliveries(weeks = 8) {
  const { data, error, isLoading } = useSWR<{ weeks: WeekRow[] }>(
    `/api/metrics/deliveries/weekly?weeks=${weeks}`,
    fetcher,
    { refreshInterval: 300_000 }
  );
  return { weeks: data?.weeks ?? [], error, isLoading };
}
