# A.N.I. (Agricultural Network & Inventory)

IT317 – G5 · IM2 Project
Stack: Django (templates) + PostgreSQL / Supabase.

**Progress:** Phase 1 – Account feature ✅ · Phase 2 – Core feature: **QR-Based Proxy Logging (equipment rentals & crop drop-offs)** ✅

## Roles

| Role | How they sign up | Lands on |
|---|---|---|
| **Cooperative Admin** | Registers and enters a cooperative name; the cooperative gets an 8-character **join code** | `/dashboard/admin/` |
| **Farmer** | Registers with the cooperative's join code | `/dashboard/farmer/` |

## Core feature: QR-Based Proxy Logging (Equipment Rentals & Crop Drop-offs)

Smallholder farmers don't need smartphones: each farmer gets a printed **QR ID card** (the QR holds
their Farmer ID, e.g. `ANI-00012`). At the cooperative hub the **Cooperative Admin scans the card** and
logs a **crop drop-off** or an **equipment rental** on the farmer's behalf. Everything is stored in
PostgreSQL/Supabase and rolls up into yield totals and a searchable transaction log.

**Flow**

1. Admin adds the cooperative's machines (*Machinery*) and prints farmer cards (*QR ID Cards*).
2. At the hub the farmer shows the card; the admin opens *QR Logging* and **scans** it (phone camera,
   handheld USB scanner, or type the ID) → the farmer's workspace opens.
3. **Crop drop-off:** crop type, weight (kg), grade, notes → saved, yield totals update.
4. **Equipment rental:** machine + expected hours → the system checks the schedule (machine not already
   out, not reserved by someone else) → rental starts. *Log return* closes it.
5. *Transaction Log*: search/filter all rentals and drop-offs, edit or delete mistaken entries.
6. Farmers can log in to see *My Contributions*, *My QR ID* and *My Reservations*.

**Advance booking (supporting module).** Farmers can also pre-book machinery (*Browse Machinery* →
*Reserve*). The admin approves or rejects; approved bookings are respected when a walk-in rental is
logged, and the booking is marked *Completed* when the equipment is returned.

**Data model (ERD)**

```
Cooperative 1───* User (role: admin | farmer, farmer_code)
Cooperative 1───* Machine
User(farmer) 1──* CropDeposit        (logged_by → User admin)
User(farmer) 1──* EquipmentRental *──1 Machine        (reservation → Reservation, optional)
User(farmer) 1──* Reservation     *──1 Machine        (reviewed_by → User admin)
```

**CRUD**

| Entity | Create | Read | Update | Delete |
|---|---|---|---|---|
| Crop drop-off | Admin (farmer workspace) | Admin (log, dashboard), Farmer (own) | Admin (Transaction Log → Edit) | Admin |
| Equipment rental | Admin (farmer workspace) | Admin, Farmer (own) | Admin (Log return) | Admin |
| Machine | Admin | Admin, Farmer (catalog) | Admin | Admin (blocked if it has history) |
| Reservation | Farmer | Farmer (own), Admin (own cooperative) | Farmer (while pending); Admin (approve / reject / complete) | Farmer (own, once closed) |

**Validation / business rules**

- Farmer ID must belong to a farmer in the admin's own cooperative (scan / typed ID).
- Crop drop-off: crop type required; weight > 0 and ≤ 50,000 kg.
- Rental: only available machines of the cooperative; 0.5–12 expected hours; a machine that is still out
  can't be rented again; blocked if another farmer holds an approved reservation overlapping the window.
- Reservation: no past dates, ≤ 60 days ahead, 5 AM–8 PM, end after start, ≤ 10 h, no overlap with approved
  bookings, rejection needs a reason.
- Clear success / error messages on every action; destructive actions are POST-only + CSRF-protected.

**Access control.** All pages require login. Admin pages are admin-only (403 otherwise); admins only see
their own cooperative's data (404 otherwise); farmers only see their own records.

### Feature URLs

| URL | Access |
|---|---|
| `/proxy/scan/`, `/proxy/farmer/<ID>/`, `/proxy/transactions/` | Admin |
| `/proxy/cards/`, `/proxy/cards/<ID>/` (printable QR card) | Admin |
| `/proxy/my/qr/`, `/proxy/my/contributions/` | Farmer |
| `/machinery/machines/…`, `/machinery/manage/reservations/…` | Admin |
| `/machinery/catalog/`, `/machinery/reservations/…` | Farmer |

## Standard features (Phase 1)

Registration (role + join code), login / logout, role-based dashboards, profile view/edit with photo.
See `accounts/`. Account URLs: `/register/`, `/login/`, `/logout/` (POST), `/dashboard/`,
`/dashboard/admin/`, `/dashboard/farmer/`, `/profile/`, `/profile/edit/`.

## Setup

```bash
git clone <repo-url> && cd <repo>
python -m venv venv
venv\Scripts\activate            # Windows   (macOS/Linux: source venv/bin/activate)
pip install -r requirements.txt     # includes segno, used to draw the QR codes
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
Feature branches: `feature/machinery-management`, `feature/machinery-reservation`, `feature/qr-proxy-logging`.
