-- Normalize driver identifiers and enforce one-to-one assignments.
UPDATE chauffeurs
SET permis_numero = NULLIF(UPPER(BTRIM(permis_numero)), '');

CREATE UNIQUE INDEX IF NOT EXISTS uq_chauffeurs_permis_numero
ON chauffeurs (permis_numero)
WHERE permis_numero IS NOT NULL;

CREATE UNIQUE INDEX IF NOT EXISTS uq_chauffeurs_camion_defaut_id
ON chauffeurs (camion_defaut_id)
WHERE camion_defaut_id IS NOT NULL;
