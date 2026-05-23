-- Database Migration for Delivery Split Workflow (Option 4)
-- Human-in-the-Loop Split Validation with IATF Traceability
-- Created: 2026-05-21

-- ============================================================================
-- 1. Delivery Splits Table
-- Stores individual sub-deliveries created from splits
-- ============================================================================
CREATE TABLE IF NOT EXISTS delivery_splits (
    id SERIAL PRIMARY KEY,
    original_delivery_id INT NOT NULL REFERENCES livraisons(id) ON DELETE CASCADE,
    parent_split_id INT REFERENCES delivery_splits(id) ON DELETE CASCADE,
    split_sequence INT NOT NULL,
    quantity INT NOT NULL,
    unit_increment INT,
    
    -- State and audit
    state VARCHAR(20) NOT NULL DEFAULT 'PROPOSED',
    proposed_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    validated_at TIMESTAMP WITH TIME ZONE,
    validated_by INT REFERENCES users(id),
    
    -- Detailed audit trail
    proposal_json JSONB,
    decision_reason TEXT,
    constraint_check_json JSONB,
    
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- Indexes for delivery_splits
CREATE INDEX idx_delivery_splits_original_delivery_id ON delivery_splits(original_delivery_id);
CREATE INDEX idx_delivery_splits_state ON delivery_splits(state)
    WHERE state IN ('PROPOSED', 'VALIDATED');
CREATE INDEX idx_delivery_splits_validated_by ON delivery_splits(validated_by);
CREATE INDEX idx_delivery_splits_created_at ON delivery_splits(created_at DESC);

-- ============================================================================
-- 2. Delivery Split Audits Table
-- Complete audit trail for IATF 16949 compliance
-- ============================================================================
CREATE TABLE IF NOT EXISTS delivery_split_audits (
    id SERIAL PRIMARY KEY,
    original_delivery_id INT NOT NULL REFERENCES livraisons(id) ON DELETE CASCADE,
    
    -- State progression
    state VARCHAR(20) NOT NULL,
    detected_at TIMESTAMP WITH TIME ZONE NOT NULL,
    
    -- Proposal (algorithm output)
    proposal_json JSONB NOT NULL,
    max_vehicle_capacity INT NOT NULL,
    proposed_splits_count INT NOT NULL,
    
    -- Decision (human input)
    decision_action VARCHAR(20),  -- VALIDATE, MODIFY, REJECT
    decision_reason TEXT,
    decided_by INT REFERENCES users(id),
    decided_at TIMESTAMP WITH TIME ZONE,
    
    -- Modifications
    modified_quantities_json JSONB,
    
    -- System integration
    linked_sub_deliveries_json JSONB,
    is_integrated_to_vrptw BOOLEAN DEFAULT FALSE,
    vrptw_replan_triggered_at TIMESTAMP WITH TIME ZONE,
    
    -- Exception handling
    exception_alert_created BOOLEAN DEFAULT FALSE,
    exception_alert_id VARCHAR(100),
    
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- Indexes for delivery_split_audits
CREATE INDEX idx_delivery_split_audits_original_delivery_id 
    ON delivery_split_audits(original_delivery_id);
CREATE INDEX idx_delivery_split_audits_state ON delivery_split_audits(state)
    WHERE state IN ('DETECTED', 'PROPOSED');
CREATE INDEX idx_delivery_split_audits_decided_by ON delivery_split_audits(decided_by);
CREATE INDEX idx_delivery_split_audits_created_at ON delivery_split_audits(created_at DESC);
CREATE INDEX idx_delivery_split_audits_detected_at ON delivery_split_audits(detected_at DESC);

-- ============================================================================
-- 3. Constraints and Validation
-- ============================================================================

-- Ensure states are valid
ALTER TABLE delivery_splits 
ADD CONSTRAINT valid_split_state 
CHECK (state IN ('PROPOSED', 'VALIDATED', 'MODIFIED', 'REJECTED', 'PLANNED', 'EXCEPTION'));

ALTER TABLE delivery_split_audits
ADD CONSTRAINT valid_audit_state
CHECK (state IN ('DETECTED', 'PROPOSED', 'VALIDATED', 'MODIFIED', 'REJECTED', 'PLANNED', 'EXCEPTION'));

-- Ensure decision action is valid
ALTER TABLE delivery_split_audits
ADD CONSTRAINT valid_decision_action
CHECK (decision_action IS NULL OR decision_action IN ('VALIDATE', 'MODIFY', 'REJECT'));

-- ============================================================================
-- 4. Comments for documentation
-- ============================================================================

COMMENT ON TABLE delivery_splits IS 'Individual sub-deliveries from split operations, linked to originating delivery';
COMMENT ON COLUMN delivery_splits.state IS 'Current state in split lifecycle: PROPOSED, VALIDATED, MODIFIED, REJECTED, PLANNED, EXCEPTION';
COMMENT ON COLUMN delivery_splits.proposal_json IS 'Snapshot of proposed split data';
COMMENT ON COLUMN delivery_splits.constraint_check_json IS 'Validation checks passed (palette multiples, capacity, etc.)';

COMMENT ON TABLE delivery_split_audits IS 'Complete audit trail for each split decision - IATF 16949 compliance';
COMMENT ON COLUMN delivery_split_audits.state IS 'State progression: DETECTED -> PROPOSED -> (VALIDATED|MODIFIED|REJECTED) -> PLANNED|EXCEPTION';
COMMENT ON COLUMN delivery_split_audits.decision_action IS 'Manager decision: VALIDATE (accept), MODIFY (adjust quantities), REJECT (exceptional transport)';
COMMENT ON COLUMN delivery_split_audits.decided_by IS 'User ID of transport manager making decision';
COMMENT ON COLUMN delivery_split_audits.exception_alert_created IS 'Whether external transport service was alerted (REJECT case)';

-- ============================================================================
-- 5. Example data for testing (optional, remove for production)
-- ============================================================================

-- INSERT INTO delivery_splits (original_delivery_id, split_sequence, quantity, state)
-- VALUES (1, 1, 8000, 'PROPOSED');

-- INSERT INTO delivery_split_audits (original_delivery_id, state, detected_at, proposal_json, max_vehicle_capacity, proposed_splits_count)
-- VALUES (1, 'DETECTED', CURRENT_TIMESTAMP, '{}', 12000, 2);
