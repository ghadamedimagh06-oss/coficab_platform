# Option 4 - Architecture Diagram

## System Components Flow

```
┌─────────────────────────────────────────────────────────────────────────┐
│                        COFICAB PLATFORM - OPTION 4                      │
│                  Human-in-the-Loop Split Decision Workflow              │
└─────────────────────────────────────────────────────────────────────────┘

┏━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┓
┃ 1. WATCHDOG / MANUAL TRIGGER (T=0)                                    ┃
┃    Auto at 15:00 OR Manual "Propose Split" button                     ┃
┗━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┛
                                    ↓
                    POST /api/planning/oversized/{id}/propose-split


┏━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┓
┃ 2. BACKEND API - DETECTION & PROPOSAL                                 ┃
┣━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┫
┃                                                                        ┃
┃  ┌─────────────────────────────────────────────────────────────┐     ┃
┃  │ Step 1: Fetch Livraison from DB                            │     ┃
┃  │   - delivery_id, quantity, client, notes                   │     ┃
┃  └─────────────────────────────────────────────────────────────┘     ┃
┃                            ↓                                          ┃
┃  ┌─────────────────────────────────────────────────────────────┐     ┃
┃  │ Step 2: Check if oversized                                 │     ┃
┃  │   - quantity > max_vehicle_capacity (12000) ?             │     ┃
┃  │   - YES: Continue  / NO: Return 200 "no_split_needed"    │     ┃
┃  └─────────────────────────────────────────────────────────────┘     ┃
┃                            ↓                                          ┃
┃  ┌─────────────────────────────────────────────────────────────┐     ┃
┃  │ Step 3: ALGORITHM - SplitStrategy.compute_split()         │     ┃
┃  │   • Input: qty=28000, capacity=12000, unit_incr=24        │     ┃
┃  │   • Logic:                                                 │     ┃
┃  │     - n_splits = ceil(28000/12000) = 3                   │     ┃
┃  │     - base_qty = floor(28000/3/24)*24 = 8000             │     ┃
┃  │     - Splits: [8000, 8000, 12000]                        │     ┃
┃  │   • Output: SplitProposalSchema                            │     ┃
┃  │     - proposed_sub_deliveries: [{seq:1,qty:8000}, ...]   │     ┃
┃  │     - constraint_check: [✓ OK, ✓ OK, ✓ OK]               │     ┃
┃  └─────────────────────────────────────────────────────────────┘     ┃
┃                            ↓                                          ┃
┃  ┌─────────────────────────────────────────────────────────────┐     ┃
┃  │ Step 4: Create audit record in DB                          │     ┃
┃  │   DeliverySplitAudit {                                      │     ┃
┃  │     state: DETECTED → PROPOSED                             │     ┃
┃  │     proposal_json: {...full proposal...}                   │     ┃
┃  │     detected_at: NOW                                       │     ┃
┃  │   }                                                         │     ┃
┃  └─────────────────────────────────────────────────────────────┘     ┃
┃                            ↓                                          ┃
┃  ┌─────────────────────────────────────────────────────────────┐     ┃
┃  │ Step 5: Publish notification                               │     ┃
┃  │   Redis Pub/Sub: alerts:supervisor                         │     ┃
┃  │   Payload: {type: "OVERSIZED_DELIVERY", delivery_id, ...} │     ┃
┃  └─────────────────────────────────────────────────────────────┘     ┃
┃                            ↓                                          ┃
┃  Response: {                                                          ┃
┃    "status": "proposed",                                              ┃
┃    "audit_id": 42,                                                    ┃
┃    "proposal": {...},                                                 ┃
┃    "actions": ["VALIDATE", "MODIFY", "REJECT"]                       ┃
┃  }                                                                     ┃
┗━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┛
                                    ↓
            ┌─────────────────────────────────────────┐
            │ FRONTEND - Real-time Alert (Redis Sub)  │
            │ OR Polling every 30s                    │
            └─────────────────────────────────────────┘
                                    ↓
            ┌─────────────────────────────────────────┐
            │ OversizedDeliveryAlert widget shows:    │
            │ - "Livraison #12 - 28000 unités"       │
            │ - "3 splits proposés"                   │
            │ - "Bouton DÉCIDER"                      │
            └─────────────────────────────────────────┘


┏━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┓
┃ 3. FRONTEND - TRANSPORT MANAGER DECISION (T=90s)                      ┃
┣━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┫
┃                                                                        ┃
┃  User clicks "DÉCIDER" button                                         ┃
┃                            ↓                                          ┃
┃  SplitDecisionModal opens:                                            ┃
┃  ┌────────────────────────────────────────────────┐                  ┃
┃  │ Décision sur Split de Livraison               │                  ┃
┃  │                                                │                  ┃
┃  │ Livraison #12: 28000 unités                   │                  ┃
┃  │                                                │                  ┃
┃  │ Proposition de l'algorithme:                  │                  ┃
┃  │ Capacité max: 12000                           │                  ┃
┃  │ Splits proposés: 3                            │                  ┃
┃  │ ✓ Somme OK  ✓ Capacité OK  ✓ Bobine OK       │                  ┃
┃  │                                                │                  ┃
┃  │  ┌──────────┬──────────┬──────────┐           │                  ┃
┃  │  │VALIDER   │MODIFIER  │REJETER   │           │                  ┃
┃  │  │(Vert)    │(Ambre)   │(Rouge)   │           │                  ┃
┃  │  └──────────┴──────────┴──────────┘           │                  ┃
┃  │                                                │                  ┃
┃  │ [User selects VALIDER]                        │                  ┃
┃  │                                                │                  ┃
┃  │ Justification:                                │                  ┃
┃  │ ┌────────────────────────────────────────┐    │                  ┃
┃  │ │ Split standard conforme                │    │                  ┃
┃  │ └────────────────────────────────────────┘    │                  ┃
┃  │                                                │                  ┃
┃  │ [ANNULER]          [CONFIRMER LA DÉCISION]    │                  ┃
┃  └────────────────────────────────────────────────┘                  ┃
┃                            ↓                                          ┃
┃         POST /api/planning/oversized/12/decision                      ┃
┃         {                                                             ┃
┃           "delivery_id": 12,                                          ┃
┃           "action": "VALIDATE",                                       ┃
┃           "reason": "Split standard conforme"                         ┃
┃         }                                                             ┃
┗━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┛


┏━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┓
┃ 4. BACKEND API - DECISION PROCESSING (T=120s)                         ┃
┣━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┫
┃                                                                        ┃
┃  ACTION = VALIDATE (Accept proposal)                                  ┃
┃                            ↓                                          ┃
┃  ┌─────────────────────────────────────────────────────────────┐     ┃
┃  │ Step 1: Fetch audit record                                 │     ┃
┃  │   DeliverySplitAudit.state == PROPOSED                      │     ┃
┃  └─────────────────────────────────────────────────────────────┘     ┃
┃                            ↓                                          ┃
┃  ┌─────────────────────────────────────────────────────────────┐     ┃
┃  │ Step 2: For each proposed_sub_delivery:                    │     ┃
┃  │   Create DeliverySplit record                              │     ┃
┃  │   ├─ original_delivery_id: 12                              │     ┃
┃  │   ├─ split_sequence: 1, 2, 3                               │     ┃
┃  │   ├─ quantity: 8000, 8000, 12000                           │     ┃
┃  │   ├─ state: VALIDATED                                      │     ┃
┃  │   ├─ validated_by: user_id                                 │     ┃
┃  │   ├─ validated_at: NOW                                     │     ┃
┃  │   └─ constraint_check_json: [✓ OK, ...]                    │     ┃
┃  │                                                             │     ┃
┃  │   → Created IDs: [301, 302, 303]                           │     ┃
┃  └─────────────────────────────────────────────────────────────┘     ┃
┃                            ↓                                          ┃
┃  ┌─────────────────────────────────────────────────────────────┐     ┃
┃  │ Step 3: Update audit record                                │     ┃
┃  │   state: VALIDATED                                         │     ┃
┃  │   decision_action: VALIDATE                                │     ┃
┃  │   decided_by: user_id (manager)                            │     ┃
┃  │   decided_at: NOW                                          │     ┃
┃  │   linked_sub_deliveries_json: [301, 302, 303]              │     ┃
┃  └─────────────────────────────────────────────────────────────┘     ┃
┃                            ↓                                          ┃
┃  ┌─────────────────────────────────────────────────────────────┐     ┃
┃  │ Step 4: TRIGGER OR-TOOLS REPLAN                            │     ┃
┃  │   await optimizer.replan_with_new_state()                  │     ┃
┃  │   OR                                                        │     ┃
┃  │   await pubsub.publish("optimizer:replan_trigger", ...)    │     ┃
┃  │                                                             │     ┃
┃  │   → New graph with 3 separate delivery nodes               │     ┃
┃  │   → Reoptimize routes (VRPTW)                              │     ┃
┃  │   → Generate new planning                                  │     ┃
┃  └─────────────────────────────────────────────────────────────┘     ┃
┃                            ↓                                          ┃
┃  Response: {                                                          ┃
┃    "status": "validated",                                             ┃
┃    "delivery_id": 12,                                                 ┃
┃    "sub_deliveries_created": 3,                                       ┃
┃    "sub_delivery_ids": [301, 302, 303],                               ┃
┃    "message": "Split approuvé: 3 sous-livraisons créées"              ┃
┃  }                                                                     ┃
┗━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┛
                                    ↓
                    ┌──────────────────────────┐
                    │ Dashboard refreshes      │
                    │ Widget updates:          │
                    │ "✓ Livraison validée"   │
                    │ Split removed from list │
                    └──────────────────────────┘


┏━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┓
┃ 5. DATABASE AUDIT TRAIL (IATF 16949)                                  ┃
┣━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┫
┃                                                                        ┃
┃  delivery_split_audits:                                               ┃
┃  ┌─────────────────────────────────────────────────────────────┐     ┃
┃  │ id | delivery | state | detected_at | decision_action      │     ┃
┃  │ ────────────────────────────────────────────────────────── │     ┃
┃  │142 | 12       | VALIDATED | 15:00:00 | VALIDATE           │     ┃
┃  │    | decided_by: 5 | decided_at: 15:02:30                 │     ┃
┃  │    | reason: "Split standard conforme"                     │     ┃
┃  └─────────────────────────────────────────────────────────────┘     ┃
┃                                                                        ┃
┃  delivery_splits:                                                     ┃
┃  ┌─────────────────────────────────────────────────────────────┐     ┃
┃  │ id | original_id | seq | qty | state | validated_by        │     ┃
┃  │ ────────────────────────────────────────────────────────── │     ┃
┃  │301 | 12 | 1 | 8000 | VALIDATED | user_5 (timestamp)      │     ┃
┃  │302 | 12 | 2 | 8000 | VALIDATED | user_5 (timestamp)      │     ┃
┃  │303 | 12 | 3 | 12000 | VALIDATED | user_5 (timestamp)     │     ┃
┃  └─────────────────────────────────────────────────────────────┘     ┃
┃                                                                        ┃
┃  ✓ Who: user_5 (Transport Manager)                                   ┃
┃  ✓ When: 15:02:30 (timestamp)                                        ┃
┃  ✓ Why: "Split standard conforme" (justification)                    ┃
┃  ✓ What: VALIDATE action + 3 sub-deliveries created                  ┃
┃  ✓ How: All constraints passed (marked in constraint_check)          ┃
┗━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┛


┏━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┓
┃ 6. THREE DECISION PATHS                                               ┃
┣━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┫
┃                                                                        ┃
┃  PATH 1: VALIDATE (Green)                                             ┃
┃  ──────────────────────                                               ┃
┃  ✓ Accept proposal as-is                                              ┃
┃  ✓ Create sub-deliveries with proposed quantities                     ┃
┃  ✓ State: VALIDATED                                                   ┃
┃  ✓ Trigger OR-Tools replan                                            ┃
┃  ✓ Audit: {action: VALIDATE, ...}                                     ┃
┃                                                                        ┃
┃  PATH 2: MODIFY (Amber)                                               ┃
┃  ─────────────────────                                                ┃
┃  • Adjust quantities manually                                         ┃
┃  • Validate: sum = original, each ≤ capacity, multiples OK            ┃
┃  • Create sub-deliveries with modified quantities                     ┃
┃  • State: MODIFIED                                                    ┃
┃  • Trigger OR-Tools replan                                            ┃
┃  • Audit: {action: MODIFY, modified_quantities: [...]}                ┃
┃                                                                        ┃
┃  PATH 3: REJECT (Red)                                                 ┃
┃  ────────────────                                                     ┃
┃  ✗ Decline split proposal                                             ┃
┃  ✗ Create exception alert for external transport                      ┃
┃  ✗ State: REJECTED → EXCEPTION                                        ┃
┃  ✗ NO sub-deliveries created (transport as-is)                        ┃
┃  ✗ Audit: {action: REJECT, reason: "..."}                             ┃
┃                                                                        ┃
┗━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┛


┏━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┓
┃ KEY METRICS                                                           ┃
┣━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┫
┃                                                                        ┃
┃  T=0      Watchdog detects oversized delivery (automatic 15:00)       ┃
┃  T=10s    Proposal calculated by algorithm                            ┃
┃  T=30s    Alert shown in dashboard (polling or Redis Pub/Sub)         ┃
┃  T=90s    Transport manager sees pending decision                     ┃
┃  T=120s   Manager submits decision (VALIDATE/MODIFY/REJECT)           ┃
┃  T=150s   Sub-deliveries created in DB                                ┃
┃  T=180s   OR-Tools replan triggered + new planning generated          ┃
┃                                                                        ┃
┃  TOTAL TIME: ~3 minutes (DESIGN TARGET: < 2 minutes)                  ┃
┃                                                                        ┃
┃  CRITICAL: 100% human decision - ZERO silent automation               ┃
┃            Every action logged for IATF 16949 compliance               ┃
┃                                                                        ┃
┗━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┛
```

---

## Database Schema

```sql
-- delivery_splits: Individual sub-deliveries
CREATE TABLE delivery_splits (
    id SERIAL PRIMARY KEY,
    original_delivery_id INT → FOREIGN KEY livraisons.id
    split_sequence INT,                    -- 1, 2, 3, ...
    quantity INT,                          -- 8000, 8000, 12000
    unit_increment INT,                    -- 24 (palette)
    state VARCHAR(20),                     -- VALIDATED, MODIFIED, etc.
    validated_by INT → FOREIGN KEY users.id,
    constraint_check_json JSONB,           -- validation results
    created_at TIMESTAMP
);

-- delivery_split_audits: Complete audit trail
CREATE TABLE delivery_split_audits (
    id SERIAL PRIMARY KEY,
    original_delivery_id INT → FOREIGN KEY livraisons.id
    state VARCHAR(20),                     -- DETECTED, PROPOSED, VALIDATED, etc.
    detected_at TIMESTAMP,                 -- T=0
    proposal_json JSONB,                   -- full algorithm proposal
    max_vehicle_capacity INT,              -- 12000
    decision_action VARCHAR(20),           -- VALIDATE, MODIFY, REJECT
    decided_by INT → FOREIGN KEY users.id, -- user_id
    decided_at TIMESTAMP,                  -- T=120s
    decision_reason TEXT,                  -- "Split standard conforme"
    linked_sub_deliveries_json JSONB,      -- [301, 302, 303]
    created_at TIMESTAMP
);
```

---

## API Call Sequence Diagram

```
Client                    Backend                      Database
  │                         │                            │
  ├─ POST propose-split ──→ │                            │
  │                         ├─ Fetch Livraison ─────────→ │
  │                         │                    return   │
  │                         ├─ Calculate split           │
  │                         ├─ Create audit ────────────→ │
  │                         │ DeliverySplitAudit        │
  │                         │ state=DETECTED            │
  │← Response (proposal) ── │                    return   │
  │                         │                            │
  │ [Modal shows alert]     │                            │
  │ [Transport manager      │                            │
  │  clicks DÉCIDER]        │                            │
  │                         │                            │
  ├─ POST decision ───────→ │                            │
  │ action: VALIDATE        │                            │
  │ reason: "..."          │                            │
  │                         ├─ Fetch audit ────────────→ │
  │                         │                    return   │
  │                         ├─ Create splits ──────────→ │
  │                         │ DeliverySplit (x3)        │
  │                         │ state=VALIDATED           │
  │                         ├─ Update audit ───────────→ │
  │                         │ state=VALIDATED           │
  │                         │ decided_by=user_id        │
  │                         │ linked=[301,302,303]      │
  │                         │                    return   │
  │                         ├─ Trigger OR-Tools         │
  │← Response (success) ── │                            │
  │                         │                            │
  │ [Dashboard refresh]     │                            │
  │ [Split removed from     │                            │
  │  pending list]          │                            │
  │                         │                            │
```

---

## State Machine Diagram

```
                        ┌─────────────────────┐
                        │     INITIAL         │
                        │ (No proposal yet)   │
                        └──────────┬──────────┘
                                   │
                    [Watchdog 15:00 / Manual]
                                   ↓
                        ┌─────────────────────┐
                        │    DETECTED         │
                        │ (Oversized found)   │
                        └──────────┬──────────┘
                                   │
                              [Algo runs]
                                   ↓
                        ┌─────────────────────┐
    ┌───────────────────→│    PROPOSED         │←──────────────┐
    │                    │ (Awaiting decision) │               │
    │                    └──────┬──┬──┬────────┘               │
    │                           │  │  │                       │
    │                   [User   [U │ [U                       │
    │                   chooses] s  User                      │
    │                          [U  chooses                    │
    │                              MODIFY]                   │
    │                                │                       │
    │                                ↓                       │
    │                    ┌─────────────────────┐              │
    │                    │    MODIFIED         │              │
    │                    │ (Quantities adjusted)│─────────────┘
    │                    └──────────┬──────────┘
    │                               │
    │                     [Creates sub-deliveries
    │                      + triggers OR-Tools]
    │                               ↓
    ↓                    ┌─────────────────────┐
┌──────────────┐         │    PLANNED          │
│  VALIDATED   │←────────│ (Integrated to plan)│
│ (Accepted)   │         └─────────────────────┘
└──────┬───────┘
       │
       │ [REJECT chosen]
       │
       ↓
┌─────────────────────┐
│    REJECTED         │
│ (Exceptional        │ → Creates exception alert
│  transport req'd)   │    for external service
└─────────────────────┘

```

---

## Frontend Component Hierarchy

```
Dashboard (parent)
├── OversizedDeliveryAlert (widget)
│   ├── Alert header (red banner)
│   ├── Pending splits list
│   │   └── Split item
│   │       ├── Delivery info
│   │       ├── Constraints
│   │       └── [DÉCIDER] button
│   │
│   └── SplitDecisionModal (modal - renders on top)
│       ├── Header with delivery info
│       ├── Proposal summary
│       │   ├── Capacity info
│       │   └── Constraint checks
│       ├── Decision buttons
│       │   ├── [VALIDER] (green)
│       │   ├── [MODIFIER] (amber)
│       │   └── [REJETER] (red)
│       ├── Conditional content
│       │   └── Quantity editor (if MODIFY selected)
│       ├── Reason textarea
│       └── Footer
│           ├── [ANNULER]
│           └── [CONFIRMER LA DÉCISION]
│
└── Other dashboard components
```

---

## Performance Optimization

```
Bottleneck            Solution                    Target
──────────────────────────────────────────────────────────
Detection (Watchdog)  Async background process   10s
Proposal calculation  Algorithm O(n) time        5s
Database insert       Batch operations           2s
API response          JSON streaming             1s
Dashboard update      Redis Pub/Sub               <1s
Modal display         Client-side rendering      <1s
Decision processing   Async queue               <10s
Sub-delivery creation Bulk insert               <5s
OR-Tools trigger      Message queue             <2s
─────────────────────────────────────────────────────────
TOTAL TARGET:         < 2 minutes (120s)
```
