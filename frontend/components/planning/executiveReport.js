// Builds a polished, printable Executive / ESG report from a generated plan and
// its ESG payload, then opens it in a new window and triggers the print dialog
// (browser "Save as PDF"). No backend or extra deps — pure client-side HTML.

function n(v, d = 0) {
  if (v === null || v === undefined || Number.isNaN(Number(v))) return '—';
  return Number(v).toLocaleString(undefined, { maximumFractionDigits: d });
}

function esc(s) {
  return String(s ?? '').replace(/[&<>"]/g, (c) => (
    { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c]
  ));
}

function planTotals(plan) {
  const trucksUsed = (plan.trucks || []).filter((t) => t.trips && t.trips.length);
  let stops = 0;
  let positions = 0;
  for (const t of trucksUsed) {
    for (const trip of t.trips) {
      for (const s of trip.stops || []) {
        stops += 1;
        positions += Number(s.quantity_positions || s.position_count || 0);
      }
    }
  }
  return {
    trucksUsed: trucksUsed.length,
    stops,
    positions,
    unassigned: (plan.unassigned || []).length,
  };
}

function fleetRows(plan) {
  return (plan.trucks || [])
    .filter((t) => t.trips && t.trips.length)
    .map((t) => {
      let stops = 0;
      let positions = 0;
      for (const trip of t.trips) {
        for (const s of trip.stops || []) {
          stops += 1;
          positions += Number(s.quantity_positions || s.position_count || 0);
        }
      }
      return `<tr>
        <td>${esc(t.truck_label)}</td>
        <td style="text-align:right">${t.trips.length}</td>
        <td style="text-align:right">${stops}</td>
        <td style="text-align:right">${n(positions)} / ${n(t.capacity_positions)}</td>
      </tr>`;
    })
    .join('');
}

/**
 * @param {object} args
 * @param {object} args.plan       generated daily plan (with sustainability)
 * @param {string} args.day        ISO day
 * @param {object} [args.esg]      payload from GET /esg-report (optional)
 * @param {object} [args.confidence] payload from /confidence (optional)
 */
export function openExecutiveReport({ plan, day, esg, confidence }) {
  const s = plan.sustainability || (esg && esg.sustainability) || {};
  const cost = plan.estimated_cost_tnd || {};
  const totals = planTotals(plan);
  const win = window.open('', '_blank');
  if (!win) {
    alert('Please allow pop-ups to generate the report.');
    return;
  }

  const confidenceBlock = confidence
    ? `<div class="section">
         <h2>Plan Confidence (Monte-Carlo, ${n(confidence.runs)} runs)</h2>
         <div class="kpis">
           ${kpi('Expected OTIF', `${n(confidence.expected_otif_pct, 0)}%`)}
           ${kpi(`Reliable (≥${n(confidence.otif_target_pct)}%)`, `${n(confidence.confidence_pct, 0)}% of days`)}
           ${kpi('Finish P50 / P90', `${confidence.finish_p50 || '—'} / ${confidence.finish_p90 || '—'}`)}
         </div>
       </div>`
    : '';

  function kpi(label, value, sub = '') {
    return `<div class="kpi"><div class="kpi-label">${esc(label)}</div>
      <div class="kpi-value">${esc(value)}</div>${sub ? `<div class="kpi-sub">${esc(sub)}</div>` : ''}</div>`;
  }

  win.document.write(`<!doctype html><html><head><meta charset="utf-8">
    <title>COFICAB Operations &amp; Sustainability Report — ${esc(day)}</title>
    <style>
      * { box-sizing: border-box; }
      body { font-family: -apple-system, Segoe UI, Roboto, Arial, sans-serif; color: #1c1b22; margin: 0; padding: 40px; }
      .brand { color: #7c3aed; font-weight: 800; letter-spacing: .18em; font-size: 12px; }
      h1 { margin: 4px 0 0; font-size: 26px; }
      .meta { color: #6b7280; font-size: 13px; margin-bottom: 24px; }
      .section { margin: 26px 0; }
      h2 { font-size: 16px; border-bottom: 2px solid #ecebef; padding-bottom: 6px; }
      .kpis { display: grid; grid-template-columns: repeat(4, 1fr); gap: 12px; margin-top: 12px; }
      .kpi { border: 1px solid #ecebef; border-radius: 12px; padding: 14px; }
      .kpi-label { font-size: 11px; text-transform: uppercase; letter-spacing: .06em; color: #6b7280; }
      .kpi-value { font-size: 22px; font-weight: 700; margin-top: 6px; }
      .kpi-sub { font-size: 12px; color: #6b7280; }
      .green { color: #059669; }
      table { width: 100%; border-collapse: collapse; margin-top: 12px; font-size: 13px; }
      th, td { padding: 8px 10px; border-bottom: 1px solid #ecebef; text-align: left; }
      th { text-transform: uppercase; font-size: 11px; letter-spacing: .05em; color: #6b7280; }
      .eq { background: #ecfdf5; border-radius: 12px; padding: 12px 16px; color: #065f46; margin-top: 12px; }
      .foot { margin-top: 30px; font-size: 11px; color: #9ca3af; border-top: 1px solid #ecebef; padding-top: 10px; }
      @media print { body { padding: 16px; } .noprint { display: none; } }
    </style></head><body>
    <div class="brand">COFICAB · OPTIROUTE</div>
    <h1>Daily Operations &amp; Sustainability Report</h1>
    <div class="meta">Plan for ${esc(day)} · objective: <b>${esc(plan.objective || 'balanced')}</b> · generated ${esc(new Date().toLocaleString())}</div>

    <div class="section">
      <h2>Operations</h2>
      <div class="kpis">
        ${kpi('Deliveries served', n(totals.stops), `${n(totals.positions)} positions`)}
        ${kpi('Trucks used', n(totals.trucksUsed))}
        ${kpi('Unassigned', n(totals.unassigned))}
        ${kpi('Estimated cost', `${n(cost.total)} TND`)}
      </div>
    </div>

    <div class="section">
      <h2>Sustainability (CO₂)</h2>
      <div class="kpis">
        ${kpi('CO₂ emitted', `${n(s.co2_kg)} kg`)}
        ${kpi('CO₂ saved', `${n(s.co2_saved_kg)} kg`, `${n(s.co2_saved_pct, 1)}% vs manual`)}
        ${kpi('Fuel', `${n(s.fuel_liters)} L`)}
        ${kpi('Distance saved', `${n(s.distance_saved_km)} km`)}
      </div>
      <div class="eq">🌳 Equivalent to <b>${n(s.trees_year_equivalent, 1)}</b> trees absorbing a year of CO₂,
        or <b>${n(s.car_km_equivalent)}</b> km of car travel avoided.</div>
    </div>

    ${confidenceBlock}

    <div class="section">
      <h2>Fleet breakdown</h2>
      <table>
        <thead><tr><th>Truck</th><th style="text-align:right">Trips</th><th style="text-align:right">Stops</th><th style="text-align:right">Positions / cap</th></tr></thead>
        <tbody>${fleetRows(plan)}</tbody>
      </table>
    </div>

    <div class="foot">
      Baseline for CO₂ savings = every delivery served by its own direct depot→client→depot round trip (no consolidation).
      Figures derived from the OR-Tools VRPTW plan. This report was generated automatically by the COFICAB Optiroute platform.
    </div>

    <script>window.onload = function(){ setTimeout(function(){ window.print(); }, 300); };</script>
  </body></html>`);
  win.document.close();
}
