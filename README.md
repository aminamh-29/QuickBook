# QuickBook

This is the backend for an event booking app. Users can browse events, book tickets and cancel them. There is also a referral system where each user gets placed in a binary tree under the person who referred them, and a small dashboard for staff.

The API is built with Django REST Framework and uses token authentication. The staff dashboard is made with normal Django views, templates and Bootstrap 5. I did not use the Django admin.

Made with Python 3.12+, Django 6.1, Django REST Framework, SQLite, drf-spectacular and django-filter.

## How to run it locally

You need Python 3.12 or newer installed.

1. Create a virtual environment and activate it

```bash
python -m venv venv
venv\Scripts\activate
```

On macOS or Linux use `source venv/bin/activate` for the second line.

2. Install the requirements

```bash
pip install -r requirements.txt
```

3. Create the database

```bash
python manage.py migrate
```

4. Create a staff user. You need this to log in to the dashboard, because the dashboard only allows users with `is_staff=True` and `createsuperuser` sets that.

```bash
python manage.py createsuperuser
```

5. Start the server

```bash
python manage.py runserver
```

Now open:

- Swagger docs: http://127.0.0.1:8000/api/docs/
- OpenAPI schema: http://127.0.0.1:8000/api/schema/
- Staff dashboard: http://127.0.0.1:8000/dashboard/ (the login page is `/dashboard/login/`)

If you are not logged in, the dashboard redirects you to the login page. If you are logged in but not staff, you get a 403.

## Demo data

If you want some data to play with, run this after migrating:

```bash
python manage.py seed_demo
```

It creates 8 customers in two referral trees (`alice` is the root of the bigger one), 3 vendors, 6 events in different districts of Kerala, and a few bookings. One event is sold out and one booking is cancelled. All the demo customers use the password `Demo@12345` with their username. You can run it more than once without getting duplicates.

## API endpoints

Every endpoint except register and login needs an `Authorization: Token <key>` header. You get the key when you log in.

| Method | Endpoint | What it does |
| --- | --- | --- |
| POST | `/api/auth/register/` | Register a user (`referral_code` is optional) |
| POST | `/api/auth/login/` | Log in and get a token |
| POST | `/api/auth/logout/` | Log out, deletes the token |
| GET | `/api/events/` | List events |
| GET | `/api/events/<id>/` | Get one event |
| POST | `/api/bookings/` | Book tickets, body like `{"event": 1, "quantity": 2}` |
| GET | `/api/bookings/` | Your bookings |
| POST | `/api/bookings/<id>/cancel/` | Cancel a booking |
| GET | `/api/referrals/<user_id>/tree/` | Referral tree (`?depth=`, default 3, max 10) |
| GET | `/api/referrals/<user_id>/root/` | Root user of the tree |
| GET | `/api/referrals/<user_id>/stats/` | Left, right and total team count |

The events list can be filtered with `?search=`, `?vendor=`, `?min_price=`, `?max_price=`, `?date_from=`, `?date_to=`, `?available=true` and `?ordering=`. The bookings list can be filtered with `?status=`.

Errors look like `{"detail": "...", "code": "..."}`, except validation errors, which use the normal DRF format per field. Status codes: 400 bad input, 401 not logged in, 404 not found, 409 conflict (not enough seats or already cancelled), 429 too many requests.

Example request:

```bash
curl -X POST http://127.0.0.1:8000/api/auth/register/ \
  -H "Content-Type: application/json" \
  -d '{"username":"alice","email":"alice@example.com","password":"Str0ng-pass!"}'
```

## Project folders

```
config/      settings, main urls, exception handler
accounts/    custom user model and auth API
events/      Vendor and Event models, event API
bookings/    Booking model, booking API, seat logic in services.py
referrals/   tree placement, tree/root/stats API
dashboard/   staff dashboard (views, forms, templates)
```

The main logic is in the `services.py` file of each app. The views only check the input, call the service and return the response.

## Some notes on how it works

Overselling: booking and cancelling run inside `transaction.atomic()` and lock the event row using `select_for_update()`. SQLite ignores row locks but only allows one writer at a time, so it is still safe, and it will also work if you switch to PostgreSQL. I also added database constraints (`available_seats <= total_seats` and quantity at least 1) in case something goes wrong in the code.

Referral tree: a new user goes into the first free spot found by searching level by level (BFS) from the referrer, left side first. There is a unique constraint on `(parent, position)` so a node can never get two children on the same side. If two signups clash, one of them is retried automatically. `referrer` (who invited the user) and `parent` (where the user sits in the tree) are saved separately.

Rate limits: 100 requests per hour for anonymous users, 1000 per hour for logged in users, and 10 per minute for login and register.

Vendors are just records that staff manage, they cannot log in. A vendor that has events cannot be deleted, you have to deactivate it.

## Running the tests

```bash
python manage.py test
```

The tests check seat counts, booking from multiple threads at the same time, invalid booking and cancel requests, referral placement (left, right and BFS order), the tree/root/stats endpoints and access to the dashboard.
