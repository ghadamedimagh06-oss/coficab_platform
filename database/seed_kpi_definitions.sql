-- KPI catalog — 8 official Coficab indicators
-- direction UP  = green_min / yellow_min thresholds (higher is better)
-- direction DOWN = green_max / yellow_max thresholds (lower is better)

INSERT INTO kpi_definition (code, nom, description, unite, frequence, direction, target_2025, green_min, yellow_min, green_max, yellow_max)
VALUES
  ('R4-06',    'OTIF',                        'On-Time In-Full delivery rate',              '%',      'monthly', 'UP',   96,    94,    92,    NULL, NULL),
  ('R4-02',    'OTD',                         'On-Time Delivery rate',                      '%',      'monthly', 'UP',   96,    94,    92,    NULL, NULL),
  ('R4-02-PF', 'Premium Freight Cost',        'Extra transport cost (EUR)',                 'EUR',    'monthly', 'DOWN', 1500,  NULL,  NULL,  2500, 3500),
  ('R4-03',    'Premium Freight Occurrences', 'Number of premium freight missions',         'Nb',     'monthly', 'DOWN', 1,     NULL,  NULL,  3,    5   ),
  ('R4-13',    'Fuel Consumption Efficiency', 'Fuel used per tonne-kilometre',              'mL/T.km','monthly', 'DOWN', 140,   NULL,  NULL,  160,  180 ),
  ('R5-10',    'Logistics Cost',              'Total logistics cost per tonne transported', '€/T',    'monthly', 'DOWN', 16,    NULL,  NULL,  18,   20  ),
  ('R4-12',    'Customer Incidents / MKm',   'Client logistics incidents per MKm sold',    'Nb',     'monthly', 'DOWN', 13,    NULL,  NULL,  14,   15  ),
  ('R4',       'Load Efficiency Rate',        'Truck load utilisation rate',                '%',      'daily',   'UP',   NULL,  80,    70,    NULL, NULL)
ON CONFLICT (code) DO NOTHING;
