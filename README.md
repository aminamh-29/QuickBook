# QuickBook

Backend for an event booking platform: REST APIs (Django REST Framework, token
auth), a binary referral network, and a custom staff dashboard (regular Django
views and templates, Bootstrap 5). Django's built-in admin is **not** used.

## Stack
Python 3.12+ · Django 6.1 · Django REST Framework · SQLite · drf-spectacular · django-filter

## Local setup

```bash
# 1. Create and activate a virtual environment
python -m venv venv
venv\Scripts\activate            # Windows
# source venv/bin/activate       # macOS / Linux

# 2. Install dependencies
pip install -r requirements.txt

# 3. Create the database
python manage.py migrate

# 4. Create a staff user (needed for the dashboard)
python manage.py createsuperuser

# 5. Run the server
python manage.py runserver
```

`createsuperuser` sets `is_staff=True`, which is what the dashboard checks.

## Where things are

| What | URL |
| --- | --- |
| Swagger UI | http://127.0.0.1:8000/api/docs/ |
| OpenAPI schema | http://127.0.0.1:8000/api/schema/ |
| Staff dashboard | http://127.0.0.1:8000/dashboard/ (login at `/dashboard/login/`) |

The dashboard is staff-only: anonymous visitors are redirected to the login
page, and signed-in non-staff users get a 403.

## API overview

All endpoints except register/login require the header
`Authorization: Token <key>`.

| Method | Route | Purpose |
| --- | --- | --- |
| POST | `/api/auth/register/` | Register (optional `referral_code`) |
| POST | `/api/auth/login/` | Log in, returns token |
| POST | `/api/auth/logout/` | Log out (deletes token) |
| GET | `/api/events/` | Browse events. `?search=`, `?vendor=`, `?min_price=`, `?max_price=`, `?date_from=`, `?date_to=`, `?available=true`, `?ordering=` |
| GET | `/api/events/<id>/` | Event details |
| POST | `/api/bookings/` | Book tickets: `{"event": 1, "quantity": 2}` |
| GET | `/api/bookings/` | Your booking history (`?status=`) |
| POST | `/api/bookings/<id>/cancel/` | Cancel a booking |
| GET | `/api/referrals/<user_id>/tree/` | Nested tree (`?depth=`, default 3, max 10) |
| GET | `/api/referrals/<user_id>/root/` | Root user of the tree |
| GET | `/api/referrals/<user_id>/stats/` | Left / right / total team counts |

Errors use a consistent body: `{"detail": "...", "code": "..."}` (validation
errors use DRF's per-field format). Status codes: 400 invalid input, 401
unauthenticated, 404 not found, 409 conflict (not enough seats, already
cancelled), 429 throttled.

Example:

```bash
curl -X POST http://127.0.0.1:8000/api/auth/register/ \
  -H "Content-Type: application/json" \
  -d '{"username":"alice","email":"alice@example.com","password":"Str0ng-pass!"}'
```

## Project structure

```
config/      settings, root URLs, shared exceptions + DRF exception handler
accounts/    custom User (referral fields), auth API
events/      Vendor and Event models, public event API
bookings/    Booking model, booking API, services.py (seat logic)
referrals/   binary tree placement, tree/root/stats, services.py, API
dashboard/   staff dashboard views, forms, templates
```

Business logic lives in each app's `services.py`; views only validate input,
call a service, and shape the response.

## Design notes

- **No overselling.** `book_tickets` and `cancel_booking` run inside
  `transaction.atomic()` and lock the event row with `select_for_update()`.
  SQLite ignores row locks but serialises writers, so this is safe there too,
  and it stays correct if you move to PostgreSQL. DB check constraints
  (`available_seats <= total_seats`, quantity >= 1) are a second safety net.
- **Referral placement.** A new user is placed in the first free slot found by
  a level-by-level (BFS) search from the referrer, left before right. A unique
  `(parent, position)` constraint guarantees a node never gets two children
  on one side; a lost race is retried automatically. `referrer` (who invited
  the user) and `parent` (where they sit in the tree) are stored separately.
- **Rate limiting.** DRF throttling: 100/hour anonymous, 1000/hour
  authenticated, 10/minute on login and register.
- **Vendors** are plain records managed by staff, not login accounts. A vendor
  with events cannot be deleted (deactivate it instead).

## Tests

```bash
python manage.py test
```

Covers seat accuracy, concurrent booking (threads), invalid booking/cancel
cases, referral placement (left, right, BFS), tree/root/stats endpoints, and
dashboard access control.
