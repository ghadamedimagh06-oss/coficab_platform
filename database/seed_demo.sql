-- Demo seed data for local development
-- Run after schema.sql and seed_kpi_definitions.sql

-- Admin user (password: admin123)
-- bcrypt hash for "admin123"
INSERT INTO users (username, email, password_hash, role)
VALUES ('admin', 'admin@coficab.local', '$2b$12$EixZaYVK1fsbw1ZfbX3OXePaWxn96p36WQoeG6Lruj3vjPGga31lW', 'admin')
ON CONFLICT (username) DO NOTHING;

INSERT INTO users (username, email, password_hash, role)
VALUES ('planner', 'planner@coficab.local', '$2b$12$EixZaYVK1fsbw1ZfbX3OXePaWxn96p36WQoeG6Lruj3vjPGga31lW', 'planner')
ON CONFLICT (username) DO NOTHING;

-- Trucks
INSERT INTO camions (plate_number, type, capacite_kg, max_palettes, status, consommation_base_l_100km)
VALUES
  ('TN-001-AB', 'SEMI',     24000, 33, 'DISPONIBLE', 32.5),
  ('TN-002-AB', 'PORTEUR',  12000, 18, 'DISPONIBLE', 24.0),
  ('TN-003-AB', 'FOURGON',   3500,  8, 'DISPONIBLE', 12.0),
  ('TN-004-AB', 'TAUTLINER',20000, 30, 'EN_MISSION', 30.0),
  ('TN-005-AB', 'SEMI',     24000, 33, 'MAINTENANCE', 32.5)
ON CONFLICT (plate_number) DO NOTHING;

-- Drivers
INSERT INTO chauffeurs (id, full_name, phone, permis_type, permis_numero, status, shift_start, shift_end)
VALUES
  (1001, 'Mohamed Ben Ali',   '+216 20 123 456', 'CE', 'CE-001-2020', 'ACTIF', '06:00', '18:00'),
  (1002, 'Ahmed Gharbi',      '+216 25 234 567', 'CE', 'CE-002-2019', 'ACTIF', '06:00', '18:00'),
  (1003, 'Hichem Mansouri',   '+216 22 345 678', 'C',  'C-003-2021',  'ACTIF', '07:00', '17:00'),
  (1004, 'Nabil Trabelsi',    '+216 29 456 789', 'CE', 'CE-004-2018', 'CONGE', '06:00', '18:00'),
  (1005, 'Slim Bouguerra',    '+216 21 567 890', 'C',  'C-005-2022',  'ACTIF', '08:00', '20:00')
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

-- Assign default trucks to drivers
UPDATE camions SET chauffeur_defaut_id = 1001 WHERE plate_number = 'TN-001-AB';
UPDATE camions SET chauffeur_defaut_id = 1002 WHERE plate_number = 'TN-002-AB';
UPDATE camions SET chauffeur_defaut_id = 1003 WHERE plate_number = 'TN-003-AB';
UPDATE chauffeurs SET camion_defaut_id = (SELECT id FROM camions WHERE plate_number = 'TN-001-AB') WHERE id = 1001;
UPDATE chauffeurs SET camion_defaut_id = (SELECT id FROM camions WHERE plate_number = 'TN-002-AB') WHERE id = 1002;
UPDATE chauffeurs SET camion_defaut_id = (SELECT id FROM camions WHERE plate_number = 'TN-003-AB') WHERE id = 1003;
