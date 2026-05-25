# Reference — UI Conventions (Do-Not-Touch List)

The visual identity of this app is **frozen**. Every implementation must preserve the look exactly. The rules below come from auditing the existing Next.js codebase under `frontend/`.

---

## Brand palette

| Token | Hex | Used for |
|---|---|---|
| **Brand purple** | `#7c3aed` | Sidebar gradient top, icon accents, primary buttons, donut segment |
| Brand purple-700 | `#6d28d9` | Sidebar gradient middle, hover states |
| Brand purple-800 | `#5b21b6` | Sidebar gradient bottom |
| **Canvas background** | `#f8f7f3` | Main page background — *every page* |
| **Title ink** | `#1a1a2e` | All headings, KPI values, axis ticks of charts |
| **Muted ink** | `#6b6b7b` | Captions, sub-labels, table secondary |
| **Border** | `#e8e5df` | Card borders, dividers |
| Pulse / skeleton | `#f0eee9` | Loading shimmer (slightly darker than canvas) |

Semantic colors (Tailwind defaults are OK):

| Token | Tailwind | Used for |
|---|---|---|
| Success | `emerald-500` `#10b981` | OTIF green band, deliver-success icon |
| Warning | `amber-500` `#f59e0b` | Yellow band, in-transit late risk |
| Danger | `red-500` `#ef4444` | Red band, breakdown badges |
| Info | `blue-500` `#3b82f6` | Routes badge, informational |
| Teal | `teal-500` `#14b8a6` | Fleet utilization card |

**Do not introduce new brand colors.** If a new state needs a color, pick from this table.

---

## Typography

- Family: system stack (Tailwind default `font-sans`). **Do not import a custom font.**
- Heading weights: `font-semibold` (not bold).
- KPI values: `text-2xl` to `text-4xl` depending on card density.
- Body: `text-sm` default, `text-xs` for captions.

---

## Layout primitives

### Card
```jsx
<div className="bg-white rounded-2xl shadow-sm border border-[#e8e5df] p-5">
  ...
</div>
```
- `rounded-2xl` (1rem), not `rounded-xl`.
- `shadow-sm`, not `shadow-md`.
- Padding: `p-5` (default) or `p-6` for large cards.
- The optional KPI band stripe (skill 09) adds `border-l-4 border-l-{emerald|amber|red}-500` — that's the **only** accepted border modification.

### Page wrapper
```jsx
<div className="p-8 min-h-screen bg-[#f8f7f3]">
  ...
</div>
```

### Headings row (page top)
```jsx
<motion.div initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }}
            className="flex flex-col gap-6 xl:flex-row xl:items-center xl:justify-between mb-8">
  <h1 className="text-2xl font-semibold text-[#1a1a2e]">...</h1>
  <div className="flex gap-3">...</div>
</motion.div>
```

### Sidebar
- Width `w-72` (18 rem).
- Fixed position, full height, purple gradient.
- Logo block: `O` glyph in `w-12 h-12` square.
- Nav items have rounded squircle icons (`rounded-2xl` icon bubble inside `rounded-2xl` link).

**Do not** change sidebar width, gradient direction, or icon shape.

---

## Iconography

Library: `lucide-react` only. Never mix icon libraries.

Common bindings (already wired):

| Domain | Icon |
|---|---|
| Truck / fleet | `Truck` |
| Route | `Route` |
| Alert | `AlertTriangle` |
| Analytics / chart | `BarChart3` |
| Drivers | `Users` |
| Clients | `Users` (also acceptable: `Building2`) |
| Calendar / planning | `CalendarDays` |
| Daily planning | `FileText` |
| Map | `Compass` |
| AI / Monitor | `Cpu` |
| Settings | `Settings` |
| Bell / notification | `Bell` |
| Clock / time | `Clock` |
| Trend up | `TrendingUp` |
| Trend down | `TrendingDown` |
| Leaf / sustainability | `Leaf` |
| Chevron | `ChevronRight`, `ChevronDown` |

---

## Charts (Recharts)

Stay with Recharts. Configurations already in use:

- `<ResponsiveContainer width="100%" height={...}>`
- `<CartesianGrid strokeDasharray="3 3" stroke="#e8e5df" />`
- `<XAxis tick={{ fill: '#6b6b7b', fontSize: 12 }} />`
- `<YAxis tick={{ fill: '#6b6b7b', fontSize: 12 }} />`
- Custom tooltip: `bg-white rounded-xl shadow-lg p-3 border border-[#e8e5df]`

Color sequences for multi-series charts:
1. `#7c3aed` (brand)
2. `#3b82f6` (info)
3. `#10b981` (success)
4. `#f59e0b` (warning)
5. `#ef4444` (danger)

**Do not** import Plotly, Chart.js, ECharts, Nivo, or any other chart library.

---

## Animation (Framer Motion)

Already used variants — reuse them:

```jsx
const container = {
  hidden: { opacity: 0 },
  show: { opacity: 1, transition: { staggerChildren: 0.08 } },
};
const item = {
  hidden: { opacity: 0, y: 20 },
  show: { opacity: 1, y: 0, transition: { duration: 0.4, ease: 'easeOut' } },
};
```

Don't introduce custom spring physics or page-transition libraries. Subtle is the rule.

---

## Status badges

Use `frontend/components/shared/StatusBadge.jsx` for every status pill. Standard variants:
- `severity="success"` — green
- `severity="warning"` — amber
- `severity="error"` — red
- `severity="info"` — blue
- `severity="neutral"` — grey

If a new status appears (e.g. `EN_COURS`), map it to one of the above. Do not invent new pill styles.

---

## Modal: `JustificationModal.jsx`

Reuse this modal for every "tell me why" prompt (reassign reason, incident cause, plan rejection). Don't duplicate the shell.

---

## Loading / empty / error placeholders

| State | Pattern |
|---|---|
| Loading | Replace inner content with `<div className="h-{n} bg-[#f0eee9] animate-pulse rounded-xl" />`, keep card shell. |
| Empty | KPI value `—`, label muted, no chart. |
| Error | Inline `<AlertTriangle className="text-red-500" size={14} />` next to label. Tooltip = error.message. |

**Never** show a full-screen spinner or a toast for KPI fetch errors. The layout must remain stable.

---

## Things to NOT add

- A theme switcher / dark mode.
- A logo redesign.
- A new font.
- A "fancier" KPI card variant.
- A different chart library.
- A global toast notification system.
- A redesigned sidebar.
- Page-level skeleton loaders that replace the whole page.
- Tooltips on every element (use sparingly: KPI cards and chart points only).
- Animations longer than 400 ms.

---

## When in doubt

Open `frontend/app/dashboard/page.jsx`. The look of the platform is whatever that page renders. Match it.
