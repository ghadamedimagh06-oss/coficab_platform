-- Normalize R4-13 thresholds to match its declared mL/T.km unit.
-- The source values 0.14 / 0.16 / 0.18 were expressed in L/T.km.
UPDATE kpi_definition
SET target_2025 = 140,
    green_max = 160,
    yellow_max = 180,
    unite = 'mL/T.km'
WHERE code = 'R4-13';
