# A.N.I. (Agricultural Network & Inventory)

IT317 – G5 · IM2 Project · **Phase 1: Project setup + Account Feature**
Stack: Django (templates for the frontend) + PostgreSQL / Supabase. No SQLite.

## 1. Setup

```bash
# 1. Virtual environment
python -m venv venv
source venv/bin/activate          # Windows: venv\Scripts\activate
pip install -r requirements.txt

# 2. Configuration
cp .env.example .env              # then edit .env (secret key + database credentials)

# 3. Create the database (local PostgreSQL)
createdb ani_db                   # or create it in pgAdmin; skip this step if using Supabase

# 4. Create tables (migrations for the custom user model are generated here)
python manage.py makemigrations accounts
python manage.py migrate

# 5. (Optional) a superuser for the Django site admin at /django-admin/
python manage.py createsuperuser

# 6. Run
python manage.py runserver
```

Commit the generated `accounts/migrations/0001_initial.py` to Git.

### Using Supabase instead of local Postgres
Supabase dashboard → **Connect** → *Session pooler*. Copy the host, port, and user into `.env`
(see the commented Supabase block in `.env.example`) and set `DB_SSLMODE=require`.
Use your database password (Project Settings → Database).

### Running the tests
```bash
python manage.py test accounts
```
Django creates a temporary `test_<name>` database, so the DB user needs the `CREATEDB` privilege.
Run the tests against your **local PostgreSQL** (Supabase usually doesn't allow creating databases).

## 2. Roles

| Role | How they sign up | Lands on |
|---|---|---|
| **Cooperative Admin** | Registers and enters a cooperative name; the cooperative is created and gets an auto-generated 8-character **join code** | `/dashboard/admin/` |
| **Farmer** | Registers with the cooperative's join code | `/dashboard/farmer/` |

Farmers receive an ID such as `ANI-00012`, reserved for the printable QR card (Sprint 4).
Superusers created with `createsuperuser` are treated as Cooperative Admins.

## 3. Requirement checklist

| Requirement | Where |
|---|---|
| Registration form, required fields, email format, unique username/email, password confirmation | `accounts/forms.py` → `RegistrationForm`; `templates/accounts/register.html` |
| Hashed passwords (Django auth, PBKDF2) | `AUTH_USER_MODEL` + `UserCreationForm.save()` |
| Success / error messages | Django messages framework, rendered in `templates/base.html` |
| Login with error on bad credentials | `AniLoginView`, `LoginForm` (username **or** email) |
| Logout ends the session | `logout_view` (POST only, CSRF-protected) |
| Logged-out users sent to login | `@login_required` / `role_required` in `accounts/decorators.py` |
| ≥ 2 roles, redirect to role dashboard | `User.Role`, `dashboard_redirect`, `LOGIN_REDIRECT_URL` |
| Role dashboards with role-specific navigation | `dashboard_admin.html`, `dashboard_farmer.html`, `dashboard_base.html` |
| Cannot open another role's dashboard by URL | `role_required(...)` → **403 Forbidden** page |
| View / edit profile (name, email, contact, photo) | `profile`, `profile_edit`, `ProfileForm` |
| Only own profile | Views always use `request.user`; no user id in the URL; role/username not editable |

## 4. URLs

| URL | Name | Access |
|---|---|---|
| `/` | `home` | public (logged-in users are redirected to their dashboard) |
| `/register/` | `register` | public |
| `/login/` | `login` | public |
| `/logout/` | `logout` | POST only |
| `/dashboard/` | `dashboard` | any logged-in user → redirects by role |
| `/dashboard/admin/` | `admin_dashboard` | Cooperative Admin only |
| `/dashboard/farmer/` | `farmer_dashboard` | Farmer only |
| `/profile/`, `/profile/edit/` | `profile`, `profile_edit` | any logged-in user (own profile) |
| `/django-admin/` | — | superusers |

## 5. Project layout

```
config/            settings (PostgreSQL), root URLs
accounts/          models, forms, views, decorators, auth backend, tests
templates/         base layout, landing page, 403/404, accounts/* pages
static/css/        stylesheet
media/             uploaded profile photos (git-ignored)
```

## 6. Not in this phase (per the sprint plan)
Change Password + recovery (Sprint 6), Proxy Operations Hub (Sprint 3), QR logging (Sprint 4),
Yield Tracker and simulated SMS (Sprint 5). Sidebar items for these are shown as "Soon".
