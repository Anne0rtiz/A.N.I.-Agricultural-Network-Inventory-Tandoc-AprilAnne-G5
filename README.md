# A.N.I. (Agricultural Network & Inventory)

IT317 – G5
Stack: Django (templates for the frontend) + PostgreSQL / Supabase.

## Roles

| Role | How they sign up | Lands on |
|---|---|---|
| **Cooperative Admin** | Registers and enters a cooperative name; the cooperative is created and gets an auto-generated 8-character **join code** | `/dashboard/admin/` |
| **Farmer** | Registers with the cooperative's join code | `/dashboard/farmer/` |

Farmers receive an ID such as `ANI-00012`, reserved for the printable QR card.
Superusers created with `createsuperuser` are treated as Cooperative Admins.

## Requirement checklist

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

## URLs

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
