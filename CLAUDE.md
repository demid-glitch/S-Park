# Project: S-Park
Paid parking platform — Web + Mobile + EV Charging

## Overview
- Web app: platform admin, parking owner, and attendant panels
- Mobile app (iOS/Android): customer parking + EV charging management
- Payments: QPay (Mongolia) + cash (recorded by attendant)
- Currency: MNT ₮
- Languages: Mongolian (default) + English

## Stack (adjust if needed)
- Backend: Python FastAPI + PostgreSQL + Redis
- Web: React + Vite + Tailwind
- Mobile: Flutter
- EV chargers: OCPP 1.6J (WebSocket) central system
- Auth: JWT + phone OTP

## Modules
1. **Parking**
   - Lots, zones, spots, tariffs (hourly / daily / monthly / free minutes)
   - Entry/exit sessions, plate-based (ANPR-ready API hook)
   - Live occupancy, reservations, subscriptions
2. **EV Charging (mobile)**
   - Charger list/map with live status (available / charging / fault)
   - Start/stop session via app (QR on charger)
   - Live kWh, duration, cost; session history
   - Tariff: per kWh + optional idle fee
3. **Payments – QPay**
   - Get access token (merchant credentials via env vars)
   - Create invoice → show QR + bank app deeplinks
   - Callback endpoint → verify with payment check API (never trust callback alone)
   - Statuses: pending / paid / failed / expired / refunded
   - Idempotent handling, full transaction log
4. **Admin panels (web)**
   - Role-based dashboards (see User roles)
   - Manage lots, tariffs, chargers, users, refunds
   - Reports export (Excel/PDF)
5. **Users**
   - Profile, vehicles (plates), payment history, notifications

## User roles
| Level | Role | Platform | Sees / does |
|---|---|---|---|
| 1 | Platform admin (us) | Web | All QPay transactions, success rate, commission, owner payouts, refunds, all lots |
| 2 | Parking owner | Web | Own lots only: free/occupied spaces live, income daily/weekly/monthly, split cash vs online (QPay), manage attendants and tariffs |
| 3 | Attendant / cashier | Web (tablet-friendly) | Assigned lot only: live spot status, open/close sessions by plate, record cash payments, own shift summary |
| 4 | User | Mobile | Parking payment (plate, duration, tariff, total, QPay QR/deeplink), EV charging (status, kWh, rate, total, stop, QPay) |

- Role-based access (RBAC); owners never see other owners' data
- Attendants: no income totals beyond own shift, no tariff or refund edits
- Cash payments recorded by attendant, tagged `cash` + attendant ID
- Online payments tagged `qpay`
- Shift close: attendant submits cash total, owner confirms

## Screen specs per role
### Level 1 — Platform admin dashboard
- KPI cards: total processed ₮, QPay success rate %, platform commission ₮, pending payouts ₮
- Transactions table: owner/lot, type (parking / EV charge), amount, status (paid / pending / refund)
- Filters: date range, lot, type, status

### Level 2 — Parking owner dashboard
- KPI cards: free spaces, occupied, capacity, occupancy %
- Income card with Daily / Weekly / Monthly toggle
- Split bar + totals: Online (QPay) vs Cash
- Attendant list + shift confirmations

### Level 3 — Attendant screen
- Spot grid with live status
- Plate search → open/close session
- Cash payment entry
- Shift summary + "Close shift" button

### Level 4 — User mobile app
- **Parking payment:** lot + spot, plate, duration, tariff, total, QPay QR, "Pay with QPay" button
- **EV charging:** charger ID + power, status, energy kWh, rate ₮/kWh, total, progress bar, "Stop" and "Pay with QPay" buttons

## Design rules
- Light theme only — NO dark theme
- NO purple gradients, no gradient-heavy UI
- Clean, minimal, high-contrast, mobile-first

## Working rules
- Edit ONLY the section/code block I specify — do not touch other files or sections
- Ask before adding new dependencies or changing project structure
- Secrets in `.env` only, never hardcoded
- Keep comments only on complex logic

## Build order
1. Backend core + DB schema + RBAC
2. QPay integration + sandbox tests
3. Parking module
4. Web panels (admin → owner → attendant)
5. Mobile app (parking)
6. OCPP server + EV charging in mobile
