# A.N.I. (Agricultural Network & Inventory)

IT317 – G5 · IM2 Project
Stack: Django (templates) + PostgreSQL / Supabase.

**Progress:** Phase 1 – Account feature ✅ · Phase 2 – Core feature: **Machinery Reservation** ✅

## Roles

| Role | How they sign up | Lands on |
|---|---|---|
| **Cooperative Admin** | Registers and enters a cooperative name; the cooperative gets an 8-character **join code** | `/dashboard/admin/` |
| **Farmer** | Registers with the cooperative's join code | `/dashboard/farmer/` |

## Core feature: Machinery Reservation

Cooperatives own shared equipment (tractors, harvesters, threshers, pumps). Farmers book it
online and the Cooperative Admin approves or rejects the request, so two farmers never end up
with the same machine at the same time.

**Flow**

1. **Admin** adds the cooperative's machines (*Machinery* in the sidebar) – create / edit / delete.
2. **Farmer** browses machines (*Browse Machinery*) and submits a reservation: machine, date,
   start/end time, field location, purpose. It starts as **Pending**.
3. **Admin** sees it under *Reservations* (with a pending-count badge and on the dashboard) and
   **approves** or **rejects** it (reason required for rejection).
4. **Farmer** sees the decision and remarks under *My Reservations* and on the dashboard. Pending
   requests can be edited; pending/approved ones can be cancelled; finished ones can be deleted.
5. **Admin** marks approved reservations **Completed** once the date has arrived.

**Data model (ERD)**

```
Cooperative 1───* User (role: admin | farmer)
Cooperative 1───* Machine           (created_by → User)
User(farmer) 1──* Reservation *──1 Machine
Reservation.reviewed_by → User (admin)
```

**CRUD**

| Entity | Create | Read | Update | Delete |
|---|---|---|---|---|
| Machine | Admin | Admin (list), Farmer (catalog) | Admin | Admin (blocked if it has reservations) |
| Reservation | Farmer | Farmer (own), Admin (own cooperative) | Farmer (while pending); Admin (approve / reject / complete) | Farmer (cancelled / rejected / completed ones) |

**Validation / business rules**

- All fields required; purpose ≥ 5 characters; hourly rate ≥ 0; machine name unique per cooperative.
- No past dates; at most 60 days ahead; operating hours 5:00 AM – 8:00 PM; end after start;
  max 10 hours per reservation.
- Only available machines from the farmer's own cooperative can be booked.
- No overlap with an **approved** booking of the same machine (checked again on approval);
  a farmer can't submit two overlapping pending requests for the same machine.
- Clear success / error messages on every action (Django messages framework).

**Security / role access**

- Every page requires login (`role_required`); wrong role → **403**.
- Reservations are linked to the farmer (`ForeignKey`). Farmers only see/modify their own records;
  admins only see records of their own cooperative (anything else → **404**).
- Mutating actions are POST-only and CSRF-protected.

### Feature URLs

| URL | Name | Access |
|---|---|---|
| `/machinery/machines/` (+ `new/`, `<id>/edit/`, `<id>/delete/`) | `machine_list`, `machine_create`, `machine_edit`, `machine_delete` | Admin |
| `/machinery/manage/reservations/` | `reservation_manage` | Admin |
| `/machinery/manage/reservations/<id>/review/` | `reservation_review` (POST) | Admin |
| `/machinery/manage/reservations/<id>/complete/` | `reservation_complete` (POST) | Admin |
| `/machinery/catalog/` | `machine_catalog` | Farmer |
| `/machinery/reservations/` (+ `new/`, `<id>/`, `<id>/edit/`, `<id>/cancel/`, `<id>/delete/`) | `my_reservations`, `reservation_create`, `reservation_detail`, `reservation_edit`, `reservation_cancel`, `reservation_delete` | Farmer (detail: also Admin) |

## Standard features (Phase 1)

Registration (role + join code), login / logout, role-based dashboards, profile view/edit with photo.
See `accounts/`. Account URLs: `/register/`, `/login/`, `/logout/` (POST), `/dashboard/`,
`/dashboard/admin/`, `/dashboard/farmer/`, `/profile/`, `/profile/edit/`.

## Setup

```bash
git clone <repo-url> && cd <repo>
python -m venv venv
venv\Scripts\activate            # Windows   (macOS/Linux: source venv/bin/activate)
pip install -r requirements.txt
```

Create `.env` in the project root (never commit it):

```
DJANGO_SECRET_KEY=change-me
DJANGO_DEBUG=True
DJANGO_ALLOWED_HOSTS=localhost,127.0.0.1
DB_NAME=postgres
DB_USER=<supabase user>
DB_PASSWORD=<supabase password>
DB_HOST=<supabase host>
DB_PORT=5432
DB_SSLMODE=require
```

Then:

```bash
python manage.py migrate
python manage.py seed_demo          # optional: demo cooperative, accounts and machines
python manage.py runserver
```

Open http://127.0.0.1:8000/.

### Demo / test accounts (created by `seed_demo`)

| Role | Username | Password |
|---|---|---|
| Cooperative Admin | `demo_admin` | `AniDemo#2026` |
| Farmer | `demo_farmer1` | `AniDemo#2026` |
| Farmer | `demo_farmer2` | `AniDemo#2026` |

### Tests

```bash
python manage.py test --settings=config.settings_test    # runs on in-memory SQLite, no DB needed
```

## Git workflow

`main` (stable) ← `develop` (integration) ← `feature/<name>` branches, merged through Pull Requests.
Feature branches so far: `feature/machinery-management`, `feature/machinery-reservation`.
