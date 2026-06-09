-- Demo seed data for local development
-- Run after schema.sql and seed_kpi_definitions.sql

-- Admin user (password: admin123)
-- bcrypt hash for "admin123"
INSERT INTO users (username, email, password_hash, role)
VALUES ('admin', 'admin@coficab.local', '$2b$12$QZvfuHmEbhuaHK8Bq.didOopBtpGTT7yDy/Qq8plM5JzvkXXA6ehy', 'admin')
ON CONFLICT (username) DO NOTHING;

INSERT INTO users (username, email, password_hash, role)
VALUES ('planner', 'planner@coficab.local', '$2b$12$QZvfuHmEbhuaHK8Bq.didOopBtpGTT7yDy/Qq8plM5JzvkXXA6ehy', 'planner')
ON CONFLICT (username) DO NOTHING;

-- Trucks (real COFICAB fleet)
INSERT INTO camions (plate_number, type, capacite_kg, max_palettes, status)
VALUES
  ('2282TU131', 'PORTEUR', 10200, 14, 'DISPONIBLE'),
  ('9524TU238', 'PORTEUR', 10230, 14, 'DISPONIBLE'),
  ('5735TU217', 'PORTEUR',  9227, 14, 'DISPONIBLE'),
  ('4331TU175', 'PORTEUR',  9200, 14, 'DISPONIBLE'),
  ('REM107627', 'SEMI',    24950, 24, 'DISPONIBLE'),
  ('626TU203',  'FOURGON',  7650, 14, 'DISPONIBLE'),
  ('7797TU218', 'PORTEUR',   925,  4, 'DISPONIBLE'),
  ('6502TU247', 'PORTEUR',  8500, 14, 'DISPONIBLE')
ON CONFLICT (plate_number) DO NOTHING;

-- Drivers (real COFICAB drivers)
INSERT INTO chauffeurs (id, full_name, phone, permis_type, permis_numero, status, shift_start, shift_end)
VALUES
  (1, 'Ala',     '+216 20 000 001', 'C', 'A001', 'ACTIF', '06:00', '18:00'),
  (2, 'Bilel',   '+216 20 000 002', 'C', 'A002', 'ACTIF', '06:00', '18:00'),
  (3, 'Hbib',    '+216 20 000 003', 'C', 'A003', 'ACTIF', '18:00', '06:00'),
  (4, 'Houssem', '+216 20 000 004', 'C', 'A004', 'ACTIF', '06:00', '18:00'),
  (5, 'Karim',   '+216 20 000 005', 'C', 'A005', 'ACTIF', '06:00', '18:00'),
  (6, 'Mehrez',  '+216 20 000 006', 'C', 'A006', 'ACTIF', '18:00', '06:00'),
  (7, 'Ridha',   '+216 20 000 007', 'C', 'A007', 'ACTIF', '06:00', '18:00')
ON CONFLICT (id) DO NOTHING;

-- Clients
INSERT INTO clients (id, nom, address, city, country, latitude, longitude, fenetre_ouverture, fenetre_fermeture)
VALUES
  (101, 'LEONI Tunisie',         'Zone Industrielle, Lot 12', 'Bizerte',    'TN', 37.2744, 9.8739,  '07:00', '16:00'),
  (102, 'Coficab France',        '15 Rue de la Paix',         'Lyon',       'FR', 45.7640, 4.8357,  '08:00', '17:00'),
  (103, 'Sumitomo Electric',     'Industrial Park, Block 5',  'Sousse',     'TN', 35.8256, 10.6369, '07:30', '15:30'),
  (104, 'Delphi Technologies',   '3 Avenue des Industries',   'Tunis',      'TN', 36.8065, 10.1815, '08:00', '17:00'),
  (105, 'Yazaki Tunisia',        'Zone Franche, Lot 8',       'Monastir',   'TN', 35.7643, 10.8113, '07:00', '16:30'),
  (106, 'Lear Corporation',      'Parc Industriel',           'Sfax',       'TN', 34.7406, 10.7603, '08:30', '17:30'),
  (107, 'Valeo Tunisie',         'Zone Industrielle Nord',    'Grombalia',  'TN', 36.6014, 10.5015, '07:00', '15:00'),
  (108, 'PKC Group',             'Industrial Zone',           'Gafsa',      'TN', 34.4250, 8.7842,  '08:00', '17:00')
ON CONFLICT (id) DO NOTHING;

-- Link drivers <-> their default trucks
UPDATE camions SET chauffeur_defaut_id = 1 WHERE plate_number = '2282TU131';
UPDATE camions SET chauffeur_defaut_id = 2 WHERE plate_number = '9524TU238';
UPDATE camions SET chauffeur_defaut_id = 3 WHERE plate_number = '5735TU217';
UPDATE camions SET chauffeur_defaut_id = 4 WHERE plate_number = '4331TU175';
UPDATE camions SET chauffeur_defaut_id = 5 WHERE plate_number = 'REM107627';
UPDATE camions SET chauffeur_defaut_id = 6 WHERE plate_number = '626TU203';
UPDATE camions SET chauffeur_defaut_id = 7 WHERE plate_number = '7797TU218';
UPDATE chauffeurs SET camion_defaut_id = (SELECT id FROM camions WHERE plate_number = '2282TU131') WHERE id = 1;
UPDATE chauffeurs SET camion_defaut_id = (SELECT id FROM camions WHERE plate_number = '9524TU238') WHERE id = 2;
UPDATE chauffeurs SET camion_defaut_id = (SELECT id FROM camions WHERE plate_number = '5735TU217') WHERE id = 3;
UPDATE chauffeurs SET camion_defaut_id = (SELECT id FROM camions WHERE plate_number = '4331TU175') WHERE id = 4;
UPDATE chauffeurs SET camion_defaut_id = (SELECT id FROM camions WHERE plate_number = 'REM107627') WHERE id = 5;
UPDATE chauffeurs SET camion_defaut_id = (SELECT id FROM camions WHERE plate_number = '626TU203') WHERE id = 6;
UPDATE chauffeurs SET camion_defaut_id = (SELECT id FROM camions WHERE plate_number = '7797TU218') WHERE id = 7;
