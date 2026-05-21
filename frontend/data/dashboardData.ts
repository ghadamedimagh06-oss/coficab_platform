export const kpiData = [
  {
    id: 'deliveries',
    label: 'Total Deliveries',
    value: '1,247',
    icon: 'truck',
    iconBg: 'rgba(124,58,237,0.1)',
    iconColor: '#7c3aed',
    trend: 12.5,
    trendLabel: 'vs last week',
    sparklineData: [40, 65, 45, 80, 55, 90, 70],
  },
  {
    id: 'routes',
    label: 'Active Routes',
    value: '18',
    icon: 'route',
    iconBg: 'rgba(59,130,246,0.1)',
    iconColor: '#3b82f6',
    trend: 3,
    trendLabel: 'this week',
    sparklineData: [12, 15, 14, 16, 18, 17, 18],
  },
  {
    id: 'delayed',
    label: 'Delayed Shipments',
    value: '7',
    icon: 'alert-triangle',
    iconBg: 'rgba(249,115,22,0.1)',
    iconColor: '#f97316',
    trend: -2,
    trendLabel: 'from yesterday',
    sparklineData: [12, 10, 11, 9, 8, 7, 7],
  },
  {
    id: 'utilization',
    label: 'Fleet Utilization',
    value: '87%',
    icon: 'bar-chart-3',
    iconBg: 'rgba(20,184,166,0.1)',
    iconColor: '#14b8a6',
    trend: 4.2,
    trendLabel: 'this month',
    sparklineData: [78, 80, 82, 85, 84, 86, 87],
  },
];

export const weeklyData = [
  { day: 'Mon', delivered: 142, planned: 150 },
  { day: 'Tue', delivered: 165, planned: 160 },
  { day: 'Wed', delivered: 128, planned: 140 },
  { day: 'Thu', delivered: 178, planned: 170 },
  { day: 'Fri', delivered: 195, planned: 180 },
  { day: 'Sat', delivered: 85, planned: 90 },
  { day: 'Sun', delivered: 42, planned: 50 },
];

export const efficiencySegments = [
  { name: 'Optimized', value: 68, color: '#7c3aed' },
  { name: 'Good', value: 18, color: '#3b82f6' },
  { name: 'Average', value: 10, color: '#f59e0b' },
  { name: 'Below Avg', value: 4, color: '#ef4444' },
];

export const fleetData = [
  { name: 'TR-01', type: 'Mercedes', utilization: 95 },
  { name: 'TR-02', type: 'Volvo', utilization: 87 },
  { name: 'TR-03', type: 'DAF', utilization: 78 },
  { name: 'TR-04', type: 'MAN', utilization: 92 },
  { name: 'TR-05', type: 'Scania', utilization: 64 },
  { name: 'TR-06', type: 'Renault', utilization: 71 },
  { name: 'TR-07', type: 'Iveco', utilization: 83 },
  { name: 'TR-08', type: 'Mercedes', utilization: 89 },
];

export const timelineEvents = [
  {
    id: '1',
    route: 'RT-2841',
    description: 'Delivered 12 packages in Casablanca zone',
    time: '14 min ago',
    status: 'completed',
  },
  {
    id: '2',
    route: 'RT-2839',
    description: 'Departed warehouse, 6 stops planned',
    time: '32 min ago',
    status: 'in-transit',
  },
  {
    id: '3',
    route: 'RT-2835',
    description: 'Delay alert: Traffic on N1 highway',
    time: '1h ago',
    status: 'delayed',
  },
  {
    id: '4',
    route: 'RT-2830',
    description: 'Route optimization saved 18km',
    time: '2h ago',
    status: 'optimized',
  },
  {
    id: '5',
    route: 'RT-2828',
    description: 'Groupage finalized: 4 clients merged',
    time: '3h ago',
    status: 'completed',
  },
];

export const alerts = [
  {
    id: '1',
    severity: 'critical',
    title: 'Route RT-2845 delayed 45min',
    description: 'Traffic congestion on A3 highway',
    time: '2 min ago',
    icon: 'alert-triangle',
    bgColor: '#fef2f2',
    borderColor: '#ef4444',
  },
  {
    id: '2',
    severity: 'warning',
    title: 'Vehicle TR-03 maintenance due',
    description: 'Scheduled inspection overdue',
    time: '1h ago',
    icon: 'clock',
    bgColor: '#fffbeb',
    borderColor: '#f59e0b',
  },
  {
    id: '3',
    severity: 'info',
    title: 'New client added to groupage',
    description: 'Client #4521 merged into route RT-2848',
    time: '3h ago',
    icon: 'info',
    bgColor: '#eff6ff',
    borderColor: '#3b82f6',
  },
];

export const donutCenterText = { value: '94%', label: 'Avg. Score' };
