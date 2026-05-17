"use client";

import { useEffect, useState } from "react";
import { getKpi, getLiveTracking } from "../services/api";
import StatCard from "../../components/cards/StatCard";
import IconBubble from '../../components/icons/IconBubble';
import BarChart from "../../components/charts/BarChart";
import ChatPanel from "../../components/chat/ChatPanel";
import { clients, drivers, trucks } from "../../data/coficabData";

export default function DashboardPage() {
  const [metrics, setMetrics] = useState({
    planning_time: 0,
    detection_latency: 0,
    data_error_rate: 0,
  });

  const [tracking, setTracking] = useState([]);
  const [chatMessages, setChatMessages] = useState([]);
  const [period, setPeriod] = useState("Week");

  useEffect(() => {
    async function load() {
      try {
        const kpi = await getKpi();
        setMetrics(kpi);

        const live = await getLiveTracking();
        const items = live?.tracking_data
          ? Object.values(live.tracking_data)
          : live || [];

        setTracking(items);

        setChatMessages((prev) => [
          "Welcome back! Live logistics data is up-to-date and ready for review.",
          ...prev,
        ]);
      } catch (err) {
        setChatMessages((prev) => [
          "Unable to load real-time data. Please verify backend connectivity.",
          ...prev,
        ]);
      }
    }

    load();
  }, []);

  const kpiCards = [
    {
      title: "Planning time",
      value: `${metrics.planning_time ?? 0}s`,
      hint: "Automated planning latency",
      icon: <IconBubble kind="clock" />,
    },
    {
      title: "Detection latency",
      value: `${metrics.detection_latency ?? 0}s`,
      hint: "Delay and anomaly detection",
      icon: <IconBubble kind="bolt" />,
    },
    {
      title: "Error rate",
      value: `${((metrics.data_error_rate ?? 0) * 100).toFixed(2)}%`,
      hint: "Quality of ingested data",
      icon: <IconBubble kind="chart" />,
    },
  ];

  const chartData = [
    { label: "Planning", value: metrics.planning_time ?? 0 },
    { label: "Detection", value: metrics.detection_latency ?? 0 },
    { label: "Errors", value: (metrics.data_error_rate ?? 0) * 100 },
  ];

  return (
    <div className="space-y-8">
      {/* HEADER */}
      <div className="rounded-[2rem] border border-[#e8e5df] bg-white p-6 shadow-sm">
        <div className="flex flex-col gap-4 xl:flex-row xl:items-center xl:justify-between">
          <div>
            <h1 className="text-3xl font-semibold text-[#1a1a2e]">
              Good morning, John
            </h1>
            <p className="mt-1 text-sm text-[#6b6b7b]">
              Monday, December 24, 2024
            </p>
          </div>

          <div className="flex flex-wrap gap-3">
            {["Week", "Month", "Year"].map((option) => (
              <button
                key={option}
                type="button"
                onClick={() => setPeriod(option)}
                className={`rounded-2xl px-4 py-2 text-sm font-semibold transition ${
                  period === option
                    ? "bg-[#7c3aed] text-white shadow-sm"
                    : "bg-[#f0ede8] text-[#6b6b7b] hover:bg-[#e5e7eb]"
                }`}
              >
                {option}
              </button>
            ))}

            <button className="rounded-2xl border border-[#e8e5df] bg-white px-4 py-2 text-sm font-semibold text-[#1a1a2e] hover:bg-[#faf8f5]">
              Export
            </button>

            <button className="rounded-2xl bg-[#7c3aed] px-5 py-2 text-sm font-semibold text-white hover:bg-[#6d28d9]">
              + New Route
            </button>
          </div>
        </div>
      </div>

      {/* MAIN GRID */}
      <div className="grid gap-8 xl:grid-cols-[minmax(0,1.8fr)_minmax(0,1fr)]">
        <section className="space-y-8">
          {/* KPI CARDS */}
          <div className="grid gap-6 sm:grid-cols-3">
            {kpiCards.map((card) => (
              <StatCard key={card.title} {...card} />
            ))}
          </div>

          {/* CHART + FLEET */}
          <div className="grid gap-6 xl:grid-cols-[1.4fr_0.6fr]">
            <div className="rounded-[2rem] border border-[#e8e5df] bg-white p-6 shadow-sm">
              <div className="mb-6 flex items-center justify-between">
                <div>
                  <p className="text-sm text-[#6b6b7b]">
                    Operational snapshot
                  </p>
                  <h2 className="text-2xl font-semibold text-[#1a1a2e]">
                    Executive overview
                  </h2>
                </div>
                <span className="rounded-full bg-[#f0ede8] px-3 py-2 text-sm text-[#6b6b7b]">
                  Real-time
                </span>
              </div>

              <BarChart
                title="Performance distribution"
                data={chartData}
                labelKey="label"
                valueKey="value"
              />
            </div>

            <div className="rounded-[2rem] border border-[#e8e5df] bg-white p-6 shadow-sm">
              <h2 className="mb-4 text-xl font-semibold text-[#1a1a2e]">
                Live fleet highlights
              </h2>

              <div className="space-y-4">
                {tracking.slice(0, 5).map((truck, i) => (
                  <div
                    key={truck.transport_id || i}
                    className="rounded-3xl border border-[#e8e5df] bg-[#faf8f5] p-4"
                  >
                    <p className="font-semibold text-[#1a1a2e]">
                      {truck.transport_id || `Vehicle ${i + 1}`}
                    </p>
                    <p className="text-sm text-[#6b6b7b]">
                      Status: {truck.status || "On time"}
                    </p>
                    <p className="text-sm text-[#6b6b7b]">
                      ETA:{" "}
                      {truck.eta_hours
                        ? `${truck.eta_hours.toFixed(1)}h`
                        : "Unknown"}
                    </p>
                  </div>
                ))}
              </div>

              <div className="mt-6 grid gap-4 sm:grid-cols-3">
                <div className="rounded-3xl border border-[#e8e5df] bg-[#faf8f5] p-4 text-sm">
                  <p className="text-[#6b6b7b]">Total clients</p>
                  <p className="mt-2 text-2xl font-semibold text-[#1a1a2e]">
                    {clients.length}
                  </p>
                </div>

                <div className="rounded-3xl border border-[#e8e5df] bg-[#faf8f5] p-4 text-sm">
                  <p className="text-[#6b6b7b]">Fleet size</p>
                  <p className="mt-2 text-2xl font-semibold text-[#1a1a2e]">
                    {trucks.length}
                  </p>
                </div>

                <div className="rounded-3xl border border-[#e8e5df] bg-[#faf8f5] p-4 text-sm">
                  <p className="text-[#6b6b7b]">Active drivers</p>
                  <p className="mt-2 text-2xl font-semibold text-[#1a1a2e]">
                    {drivers.length}
                  </p>
                </div>
              </div>
            </div>
          </div>
        </section>

        {/* SIDEBAR */}
        <aside className="space-y-6">
          <div className="rounded-[2rem] border border-slate-800 bg-[var(--surface)] p-6 shadow-xl shadow-black/20">
            <div className="mb-4 flex items-center justify-between">
              <div>
                <p className="text-sm text-slate-400">Audit readiness</p>
                <h2 className="text-lg font-semibold">
                  Change tracking is active
                </h2>
              </div>
              <span className="rounded-full bg-emerald-500/15 px-3 py-2 text-sm text-emerald-200">
                Live
              </span>
            </div>

            <div className="space-y-3 text-sm text-slate-400">
              <p>All dashboard operations are timestamped and traceable.</p>
              <p>AI planning events are captured for audit review.</p>
            </div>
          </div>

          <ChatPanel messages={chatMessages} />
        </aside>
      </div>
    </div>
  );
}