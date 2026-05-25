# 06 — Driver Dispatch & Notifications

> Goal: when a plan transitions to `VALIDE`, each assigned driver receives a structured mission brief. The dispatch service is the **only** thing allowed to send to drivers.

## KPI anchor
- **R4-02 OTD** — late dispatch = late start = late delivery. Dispatch must fire within seconds of validation.
- **R4-06 OTIF** — clear stop sequence + window per stop reduces field errors.
- **Audit** — every notification attempt is logged so a "the driver said he never got it" claim is verifiable.

---

## Channels (pick one for v1)

| Channel | Cost | Setup | Reliability | Recommendation |
|---|---|---|---|---|
| SMS via Twilio | low €€ | API key + paid number | high | **v1 recommended** |
| Local SMS gateway | free | needs hardware | medium | optional |
| WhatsApp Business | low | needs business account | high | nice-to-have |
| Email | free | SMTP creds | low (drivers don't read email) | fallback only |
| Mock console log | free | none | n/a | **dev mode** |

Default for v1: **console-log "mock notifier"** that writes the brief to a `notifications` table. Swap to Twilio later by changing one provider class.

---

## Message template

Plain text, max 4 SMS segments (~640 chars). Drivers read this on a small phone — every word matters.

```
COFICAB — Mission #2841
Date: 2026-05-25
Camion: TR-04 (Volvo)
Départ depot: 06:30

Stop 1 — Client SOMACO Casablanca
  ETA 08:15  •  1 200 kg  •  4 palettes
  Contact: Mr. El Idrissi  +212 661 12 34 56

Stop 2 — Client TANGITEX Tangier
  ETA 11:00  •  800 kg  •  3 palettes

Retour depot prévu: 16:30
Confirmer réception: répondez "OK"
```

Built by the `DispatchService.build_brief(mission)` method below.

---

## Service: `backend/app/services/dispatch_service.py`

```python
import logging
from datetime import datetime
from sqlalchemy.orm import Session
from app.models.plan import PlanVersion, PlanMission, StatutMission
from app.providers.notification import NotificationProvider, MockProvider

log = logging.getLogger(__name__)

class DispatchService:
    def __init__(self, db: Session, provider: NotificationProvider | None = None):
        self.db = db
        self.provider = provider or MockProvider()

    def dispatch_plan(self, plan: PlanVersion) -> dict:
        sent, failed = 0, 0
        for mission in plan.missions:
            ok = self._send_one(mission)
            if ok: sent += 1
            else:  failed += 1
        return {"sent": sent, "failed": failed}

    def _send_one(self, mission: PlanMission) -> bool:
        driver = mission.chauffeur
        if not driver.phone:
            log.warning("no phone for driver %s, skipping", driver.id)
            self._log_attempt(mission, "skipped", "no phone")
            return False
        brief = self.build_brief(mission)
        try:
            self.provider.send(to=driver.phone, body=brief)
            self._log_attempt(mission, "sent", None)
            return True
        except Exception as e:
            log.exception("dispatch failed for driver %s", driver.id)
            self._log_attempt(mission, "failed", str(e))
            return False

    def build_brief(self, mission: PlanMission) -> str:
        lines = []
        lines.append(f"COFICAB — Mission #{mission.id}")
        lines.append(f"Date: {mission.date_mission}")
        lines.append(f"Camion: {mission.camion.plate_number} ({mission.camion.type.value})")
        if mission.heure_sortie_prevue:
            lines.append(f"Départ: {mission.heure_sortie_prevue.strftime('%H:%M')}")
        lines.append("")
        for stop in sorted(mission.stops, key=lambda s: s.ordre_livraison):
            d = stop.demande
            c = d.client
            lines.append(f"Stop {stop.ordre_livraison} — {c.nom} {c.city or ''}".strip())
            eta_str = stop.eta_prevue.strftime('%H:%M') if stop.eta_prevue else "—"
            lines.append(f"  ETA {eta_str}  •  {int(d.quantite_kg)} kg  •  {d.nombre_palettes or 0} palettes")
            if c.numero:
                lines.append(f"  Contact: {c.numero}")
            lines.append("")
        if mission.heure_retour_prevue:
            lines.append(f"Retour: {mission.heure_retour_prevue.strftime('%H:%M')}")
        lines.append("Confirmer: répondez OK")
        return "\n".join(lines)

    def _log_attempt(self, mission, status, error):
        from app.models.notification import NotificationLog
        self.db.add(NotificationLog(
            mission_id=mission.id,
            chauffeur_id=mission.chauffeur_id,
            status=status,
            error=error,
            sent_at=datetime.utcnow(),
        ))
        self.db.commit()
```

---

## Notification provider abstraction

`backend/app/providers/notification.py`:

```python
from abc import ABC, abstractmethod
import logging

log = logging.getLogger("dispatch")

class NotificationProvider(ABC):
    @abstractmethod
    def send(self, to: str, body: str) -> None: ...

class MockProvider(NotificationProvider):
    def send(self, to: str, body: str) -> None:
        log.info("=== MOCK SMS to %s ===\n%s\n=====================", to, body)

class TwilioProvider(NotificationProvider):
    def __init__(self, account_sid: str, auth_token: str, from_number: str):
        from twilio.rest import Client
        self.client = Client(account_sid, auth_token)
        self.from_number = from_number

    def send(self, to: str, body: str) -> None:
        self.client.messages.create(body=body, from_=self.from_number, to=to)
```

Pick provider via env:
```python
# main.py
provider = MockProvider() if os.getenv("NOTIFY_PROVIDER","mock") == "mock" else \
           TwilioProvider(os.getenv("TWILIO_SID"), os.getenv("TWILIO_TOKEN"), os.getenv("TWILIO_FROM"))
```

---

## `notifications` table

Add to schema (skill 02):

```sql
CREATE TABLE notification_log (
    id           SERIAL PRIMARY KEY,
    mission_id   INTEGER NOT NULL REFERENCES plan_mission(id),
    chauffeur_id INTEGER NOT NULL REFERENCES chauffeurs(id),
    status       VARCHAR(20) NOT NULL,    -- 'sent' | 'failed' | 'skipped'
    error        TEXT,
    sent_at      TIMESTAMPTZ DEFAULT now()
);
```

---

## When dispatch fires

Exactly one trigger: `PlanningService.validate()` in skill 05. No other entry point. This means **if validation never happens, dispatch never fires** — that's the spec ("AI proposes, human approves").

Re-validation of the same plan (clicking Valider twice) is a no-op (`statut_plan == VALIDE` short-circuits).

---

## API endpoints

```
GET  /api/dispatch/missions/{mission_id}/brief    plain-text preview
POST /api/dispatch/missions/{mission_id}/resend   manual resend (planner only)
GET  /api/dispatch/logs?date=2026-05-25           list of attempts
```

---

## Anti-patterns

- ❌ Sending from the optimizer (skill 04) — that's a DRAFT, the manager hasn't approved.
- ❌ Sending from a webhook on `plan_mission` insert — couples the trigger to the table.
- ❌ Skipping the `notification_log` write. Without it you cannot prove a message went out.
- ❌ Embedding Twilio credentials in code. Use env vars, never commit secrets.

---

## Verification

Mock mode:
1. Validate a plan (skill 05). Check `[DISPATCH]` logs in the backend stdout — one block per driver.
2. `SELECT * FROM notification_log WHERE mission_id=...` → one row per mission with `status='sent'`.

Twilio mode:
1. Use a single test mission with your own phone number on `chauffeurs.phone`.
2. Validate. Confirm SMS arrives within 10s.
3. Set `phone = NULL` for one driver, validate again. That mission should show `status='skipped'`.
