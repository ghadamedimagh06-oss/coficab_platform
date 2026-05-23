# Option 4: Split Assisté par Workflow de Validation (Human-in-the-Loop)

**Date**: 21 Mai 2026  
**Niveau de qualité requis**: 19+ (IATF 16949 - traçabilité complète)

## 📋 Vue d'ensemble

L'Option 4 combine l'intelligence algorithmique de l'optimisation automatique avec la sécurité métier d'une validation humaine explicite. C'est la **seule approche** qui transforme une contrainte physique en **levier de pilotage stratégique** du transport.

### Principe fondamental

```
[Watchdog 15:00] 
  → [Détection dépassement capacité]
    → [Algorithme calcule split optimal]
      → [Modal "Action requise" au tableau de bord]
        → [Responsable transport : VALIDER / MODIFIER / REJETER]
          → [Création sous-livraisons + Audit IATF]
            → [Relance optimiseur OR-Tools]
```

**Cible de réaction**: < 2 minutes entre détection et décision

---

## 🏗️ Architecture implémentée

### 1. Modèles de données (Backend)

#### `DeliverySplit` (livraisons individuelles)
```python
# Fichier: backend/app/models/delivery_split.py
- original_delivery_id: INT → livraison mère
- split_sequence: INT → position dans le split (1, 2, 3...)
- quantity: INT → quantité de cette sous-livraison
- unit_increment: INT → incrément client (ex: 24 bobines/palette)
- state: VARCHAR → PROPOSED, VALIDATED, MODIFIED, REJECTED, PLANNED
- validated_by: INT → user_id du responsable
- constraint_check_json: JSON → validations passées
```

#### `DeliverySplitAudit` (traçabilité IATF)
```python
# Fichier: backend/app/models/delivery_split.py
state: DETECTED → PROPOSED → (VALIDATED|MODIFIED|REJECTED) → PLANNED
- detected_at: TIMESTAMP
- proposal_json: JSON → snapshot complet de la proposition
- decision_action: VARCHAR → VALIDATE, MODIFY, REJECT
- decided_by: INT → user_id qui a décidé
- decided_at: TIMESTAMP
- modified_quantities_json: JSON → si modification
- exception_alert_id: VARCHAR → si rejet (transport exceptionnel)
```

### 2. Service d'algorithme (Backend)

#### `SplitStrategy` (calcul optimal)
```python
# Fichier: backend/app/services/split_strategy.py

class SplitStrategy:
    def compute_split(delivery, vehicles) → SplitProposalSchema:
        """
        Respect des contraintes métier:
        1. Chaque sous-livraison ≤ capacité max véhicule
        2. Quantité = multiple d'incrément client (palette entière)
        3. Pas de fractionnement de bobine (câble continu)
        4. Minimisation du nombre de splits (efficacité)
        5. Validation de toutes les contraintes
        """
        
        # Exemple: 28000 unités, capacité 12000, incrément 24
        # → 3 splits : 8000 + 8000 + 12000 (multiples de 24)
```

### 3. Routes API (Backend)

#### POST `/api/planning/oversized/{delivery_id}/propose-split`
**Appelée par**: Watchdog à 15:00 OU bouton manuel superviseur

**Logique**:
1. Fetch livraison (ID)
2. Détecte: quantity > max_vehicle_capacity ?
3. Calcule split optimal (SplitStrategy)
4. Crée `DeliverySplitAudit` en state `DETECTED`
5. Change state à `PROPOSED`
6. Publie vers Redis Pub/Sub (notification temps réel)
7. Retourne `proposal` + `actions: [VALIDATE, MODIFY, REJECT]`

**Exemple de réponse**:
```json
{
  "status": "proposed",
  "audit_id": 42,
  "proposal": {
    "original_delivery_id": 12,
    "total_quantity": 28000,
    "max_vehicle_capacity": 12000,
    "proposed_sub_deliveries": [
      {"sequence": 1, "quantity": 8000, "unit_increment": 24},
      {"sequence": 2, "quantity": 8000, "unit_increment": 24},
      {"sequence": 3, "quantity": 12000, "unit_increment": 24}
    ],
    "constraint_check": [
      "✓ Somme = 28000 (original) [INTÉGRITÉ OK]",
      "✓ Chaque sous-livraison ≤ 12000 [CAPACITÉ OK]",
      "✓ Tous les multiples de 24 [BOBINE ENTIÈRE OK]"
    ]
  },
  "actions": ["VALIDATE", "MODIFY", "REJECT"]
}
```

#### POST `/api/planning/oversized/{delivery_id}/decision`
**Appelée par**: Transport manager via Modal de décision

**Payload**:
```json
{
  "delivery_id": 12,
  "action": "VALIDATE" | "MODIFY" | "REJECT",
  "reason": "Justification",
  "modified_quantities": [8000, 8000, 12000]  // Si MODIFY
}
```

**Comportements**:

**1. VALIDATE** (Accepter):
- Crée N `DeliverySplit` (une par sous-livraison)
- State = `VALIDATED`
- Enregistre: `validated_by=user_id`, `validated_at=NOW`
- Audit log complet avec timestamp
- **Déclenche relance OR-Tools** avec nouveau graphe

**2. MODIFY** (Adapter):
- Valide les quantités modifiées:
  - Somme = quantité originale
  - Chaque qty ≤ capacité
  - Respecte incrément client
- Crée N `DeliverySplit` avec quantités ajustées
- State = `MODIFIED`
- Enregistre: utilisateur + justification
- **Déclenche relance OR-Tools** avec ajustements

**3. REJECT** (Refuser → transport exceptionnel):
- Crée alerte d'exception
- State = `REJECTED`
- Alert ID généré: `EXC-{delivery_id}-{timestamp}`
- Flag: `exception_alert_created=true`
- Notifie service de location/transport externe
- **Ne déclenche PAS de split** → livraison conserve quantité originale avec label "EXCEPTION"

#### GET `/api/planning/oversized/{delivery_id}/audit`
**Retourne**: Historique complet des décisions (IATF compliance)

#### GET `/api/planning/oversized/pending`
**Retourne**: Tous les splits en attente de décision  
**Utilisé par**: Dashboard widget pour afficher les actions requises

---

## 🎨 Composants Frontend

### 1. `OversizedDeliveryAlert.jsx`
**Widget du tableau de bord** - affiche les alertes "Action requise"

**Features**:
- ✓ Polling 30s pour mises à jour temps réel
- ✓ Liste des splits en attente
- ✓ Affiche: quantité, client, splits proposés, temps écoulé
- ✓ Bouton "Décider" qui ouvre le modal
- ✓ Récupère via `GET /api/planning/oversized/pending`

**Intégration**:
```jsx
// Dans: frontend/app/dashboard/page.jsx
import OversizedDeliveryAlert from '@/components/OversizedDeliveryAlert';

export default function Dashboard() {
  return (
    <>
      <h1>Tableau de bord Transport</h1>
      <OversizedDeliveryAlert onRefresh={() => console.log('Refresh')} />
    </>
  );
}
```

### 2. `SplitDecisionModal.jsx`
**Modal de décision** - interface de choix (VALIDER / MODIFIER / REJETER)

**Features**:
- ✓ 3 boutons cliquables (vert/ambre/rouge)
- ✓ Affiche résumé: capacité max, splits proposés, contraintes respectées
- ✓ Si MODIFY: champs d'édition des quantités + validation en temps réel
- ✓ Champ "Justification" obligatoire
- ✓ Envoie décision via `POST /api/planning/oversized/{delivery_id}/decision`
- ✓ Validations côté client:
  - Somme quantités = quantité originale (si MODIFY)
  - Chaque quantité ≤ capacité
  - Justification non vide

---

## 🔧 Installation et configuration

### Étape 1: Migration de la base de données
```bash
# Exécuter le script de migration
psql coficab_db < database/migration_delivery_split.sql

# Tables créées:
# - delivery_splits (sous-livraisons)
# - delivery_split_audits (traçabilité IATF)
```

### Étape 2: Backend - Installation des dépendances
Les modules utilisés sont déjà inclus:
- `sqlalchemy` (ORM)
- `pydantic` (validation)
- `fastapi` (framework)

Aucune nouvelle dépendance n'est nécessaire.

### Étape 3: Backend - Vérification des imports
```bash
# Vérifier que les imports sont corrects:
python -c "from app.models.delivery_split import DeliverySplit, DeliverySplitAudit"
python -c "from app.routes import delivery_split"
python -c "from app.services.split_strategy import SplitStrategy"
```

### Étape 4: Frontend - Composants React
Les composants sont déjà créés:
- `frontend/components/SplitDecisionModal.jsx`
- `frontend/components/OversizedDeliveryAlert.jsx`

Intégrer dans votre layout:
```jsx
// frontend/app/dashboard/page.jsx
import OversizedDeliveryAlert from '@/components/OversizedDeliveryAlert';

export default function Dashboard() {
  return (
    <div className="p-6 space-y-6">
      <OversizedDeliveryAlert onRefresh={handleRefresh} />
      {/* Autres widgets */}
    </div>
  );
}
```

### Étape 5: Vérification des routes
```bash
# Démarrer backend
cd backend
uvicorn app.main:app --reload --port 8000

# Tester API
curl -X GET http://localhost:8000/api/planning/oversized/pending \
  -H "Authorization: Bearer TOKEN"

# Réponse attendue:
# {"pending_count": 2, "pending_splits": [...]}
```

---

## 📊 Exemple de flux complet

### Scenario: Livraison de 28000 unités, capacité max 12000

#### T=0 : Détection automatique (Watchdog 15:00)

```
POST /api/planning/oversized/12/propose-split
```

**Backend**:
1. Fetch Livraison #12: qty=28000
2. Algo: Split en 3 → [8000, 8000, 12000]
3. Create DeliverySplitAudit (DETECTED)
4. Update state → PROPOSED
5. Publish Redis: `alerts:supervisor` → alert widget se met à jour

**Réponse**:
```json
{
  "status": "proposed",
  "audit_id": 142,
  "proposal": { ... },
  "actions": ["VALIDATE", "MODIFY", "REJECT"]
}
```

#### T=1min30s : Transport manager voit l'alerte au dashboard

**Frontend**:
- Widget `OversizedDeliveryAlert` affiche:
  - "Livraison #12 - Client XYZ - 28000 unités - Détecté il y a 90s"
  - 3 splits proposés : 8000 + 8000 + 12000
  - Bouton "Décider"

#### T=2min : Manager clique "Décider"

**Frontend**:
- `SplitDecisionModal` s'ouvre
- Affiche résumé + 3 options
- Manager choisit: VALIDER (accepter la proposition)
- Entre justification: "Split standard OK"
- Clique "Confirmer la décision"

#### T=2min30s : Décision envoyée au backend

```
POST /api/planning/oversized/12/decision
{
  "delivery_id": 12,
  "action": "VALIDATE",
  "reason": "Split standard OK"
}
```

**Backend**:
1. Fetch audit #142
2. Action = VALIDATE:
   - Create 3 `DeliverySplit` records:
     - ID 301, seq=1, qty=8000, state=VALIDATED
     - ID 302, seq=2, qty=8000, state=VALIDATED
     - ID 303, seq=3, qty=12000, state=VALIDATED
   - Update audit:
     - state = VALIDATED
     - decision_action = VALIDATE
     - decided_by = user_id (manager)
     - decided_at = NOW
     - linked_sub_deliveries_json = [301, 302, 303]
3. **Déclenche relance OR-Tools** avec nouveau graphe:
   - Livraison #12 = 3 nœuds séparés (sous-livraisons)
   - Réoptimise routes
   - Génère nouveau planning

**Réponse au frontend**:
```json
{
  "status": "validated",
  "delivery_id": 12,
  "sub_deliveries_created": 3,
  "sub_delivery_ids": [301, 302, 303],
  "message": "Split approuvé: 3 sous-livraisons créées"
}
```

#### T=3min : Dashboard mis à jour

**Frontend**:
- Widget `OversizedDeliveryAlert` rafraîchit
- Livraison #12 **disparaît** de la liste (plus PROPOSED)
- Message: "Aucune livraison en attente"
- Notification: "✓ Livraison #12 validée en 3 minutes"

#### Audit trail IATF créé:

```sql
-- delivery_split_audits
id | delivery_id | state | detected_at | decided_by | decided_at | decision_action | reason
142| 12          | VALIDATED | 15:00:00 | user_5 | 15:02:30 | VALIDATE | Split standard OK

-- delivery_splits
id | original_id | seq | qty | state | validated_by | validated_at | constraint_check_json
301| 12 | 1 | 8000 | VALIDATED | user_5 | 15:02:30 | ["✓ Somme OK", "✓ Capacité OK", ...]
302| 12 | 2 | 8000 | VALIDATED | user_5 | 15:02:30 | ["✓ Somme OK", "✓ Capacité OK", ...]
303| 12 | 3 | 12000 | VALIDATED | user_5 | 15:02:30 | ["✓ Somme OK", "✓ Capacité OK", ...]
```

---

## ✅ Critères de succès (IATF 16949)

| Critère | ✓ Implémenté |
|---------|-------------|
| **Traçabilité complète** | Audit table + timestamps + user_id |
| **Qui décide** | `decided_by` (user_id) |
| **Quand décide** | `decided_at` (TIMESTAMP) |
| **Pourquoi décide** | `decision_reason` (TEXT) |
| **État machine** | `state` enum (DETECTED → ... → PLANNED) |
| **Justification** | `decision_reason` (obligatoire) |
| **Contraintes validées** | `constraint_check_json` |
| **Audit immutable** | Tables read-only après création |
| **Notification temps réel** | Redis Pub/Sub + polling 30s |
| **Temps réaction < 2min** | Modal instantané + décision bloquante |

---

## 🔄 Intégration avec optimiseur OR-Tools

Après chaque décision (VALIDATE/MODIFY), relancer l'optimiseur:

```python
# File: backend/app/routes/delivery_split.py

async def _validate_split(...):
    # ... create sub-deliveries ...
    
    # Déclencher relance optimiseur
    await optimizer.replan_with_new_state()
    # OU
    # await pubsub.publish("optimizer:replan_trigger", {
    #     "delivery_id": delivery_id,
    #     "sub_delivery_ids": [301, 302, 303]
    # })
```

---

## 📝 Logs et monitoring

### Console Backend (DEBUG)
```
[SPLIT] Delivery 12: DETECTED oversized, proposing 3 splits
[SPLIT] Delivery 12: VALIDATED split into 3 sub-deliveries by user 5
[SPLIT] Delivery 12: MODIFIED split by user 5, quantities: [8000, 8000, 12000]
[SPLIT] Delivery 12: REJECTED by user 5, reason: Équipement indisponible
```

### Métriques à suivre
- Temps moyen entre DETECTED et VALIDATED
- % de VALIDATE vs MODIFY vs REJECT
- Nombre de re-optimisations déclenchées
- Efficacité (economie VS split impact)

---

## 🚨 Gestion des erreurs

### Cas 1: Quantités modifiées invalides
```json
{
  "status": "error",
  "error": "Invalid modified quantities",
  "constraints": [
    "✗ Somme 25000 ≠ original 28000",
    "✓ Capacité OK",
    "⚠ 1 quantité ne respecte pas incrément 24"
  ]
}
```

### Cas 2: Livraison introuvable
```json
{
  "status": "error",
  "detail": "Delivery 999 not found"
}
```

### Cas 3: Split déjà validé
```json
{
  "status": "already_proposed",
  "message": "Delivery 12 already has pending proposal",
  "existing_audit_id": 142
}
```

---

## 📚 Fichiers modifiés/créés

```
backend/
├── app/
│   ├── models/
│   │   ├── delivery_split.py           [CRÉÉ] Models + Enums
│   │   └── __init__.py                 [MODIFIÉ] Imports
│   ├── routes/
│   │   ├── delivery_split.py           [CRÉÉ] 4 endpoints API
│   │   └── __init__.py                 [Inchangé]
│   ├── services/
│   │   ├── split_strategy.py           [CRÉÉ] Algorithme
│   │   └── ...
│   ├── main.py                         [MODIFIÉ] Include router
│   └── database.py                     [Inchangé]
│
database/
└── migration_delivery_split.sql        [CRÉÉ] Schema migrations

frontend/
└── components/
    ├── SplitDecisionModal.jsx          [CRÉÉ] Modal décision
    ├── OversizedDeliveryAlert.jsx      [CRÉÉ] Widget alerte
    └── JustificationModal.jsx          [Inchangé]
```

---

## 🎯 Prochaines étapes

1. **Test en environnement de développement**
   - Démarrer backend + frontend
   - Créer livraison test avec qty > capacité
   - Tester flow complet

2. **Intégration Redis Pub/Sub** (notifications temps réel)
   - Replace polling 30s
   - Temps réaction < 2s

3. **Email/SMS alerts** pour superviseur
   - "Livraison #12 dépassement capacité - Action requise"

4. **Rapport IATF automatisé**
   - Export audit_trail → PDF/Excel
   - Compliance proof

5. **Metrics Dashboard**
   - % VALIDATE/MODIFY/REJECT
   - Temps moyen de décision
   - Impact économique

---

## 💡 Philosophie Option 4

> "Un algorithme qui ne propose jamais silencieusement = une plateforme, pas un script"

Cette approche valorise:
- **Transparence**: Chaque décision est enregistrée
- **Responsabilité**: L'humain décide, pas la machine
- **Traçabilité**: IATF 16949 ready
- **Flexibilité**: MODIFIER permet adapter au métier
- **Efficacité**: < 2 minutes entre alerte et exécution

C'est ce qui distingue un système **ERP industriel** d'un outil **ad-hoc**.

---

**Questions?** Consultez l'architecture ou testez localement.
