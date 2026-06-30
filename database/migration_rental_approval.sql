CREATE TABLE IF NOT EXISTS rental_approval (
    id                 SERIAL PRIMARY KEY,
    plan_id            VARCHAR(100) NOT NULL,
    day                DATE NOT NULL,
    recommendation_id  VARCHAR(100) NOT NULL,
    rental_profile     VARCHAR(50) NOT NULL,
    estimated_cost_eur NUMERIC(10,2) NOT NULL,
    approved_by        VARCHAR(100) NOT NULL,
    created_at         TIMESTAMPTZ DEFAULT now(),
    UNIQUE (plan_id, recommendation_id)
);
CREATE INDEX IF NOT EXISTS idx_rental_approval_plan ON rental_approval(plan_id);
CREATE INDEX IF NOT EXISTS idx_rental_approval_day ON rental_approval(day);
CREATE UNIQUE INDEX IF NOT EXISTS uq_rental_approval_plan_recommendation
ON rental_approval(plan_id, recommendation_id);
