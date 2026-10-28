# QuickBook

A Django-based event booking platform with referral-based user growth and a staff dashboard.

The API is built with Django REST Framework and uses token authentication. The staff dashboard is made with normal Django views, templates, and Bootstrap 5. I did not use the Django admin.

Made with Python 3.12+, Django 6.1, Django REST Framework, SQLite, drf-spectacular and django-filter.

## Why this project exists

QuickBook combines two important business features in one system:

- event discovery and booking for end users
- referral-based customer acquisition and tree tracking

This makes it a practical backend project for demonstrating real-world logic, validation, and API design.

## Main features

- User registration and login
- Token-based authentication
- Referral codes and binary referral tree placement
- Event listing with search and filtering
- Ticket booking with seat validation
- Booking cancellation and seat restoration
- Staff dashboard for vendors, events, and users
- Swagger API documentation
- Demo data generation for local testing

## How to run it locally

You need Python 3.12 or newer installed.

### 1. Create a virtual environment and activate it

```bash
python -m venv .venv

# macOS / Linux
source .venv/bin/activate

# Windows
.\.venv\Scripts\Activate.ps1
```

### 2. Install the requirements

```bash
pip install -r requirements.txt
```

### 3. Create the database

```bash
python manage.py migrate
```

### 4. Create a staff user

```bash
python manage.py createsuperuser
```

### 5. Start the development server

```bash
python manage.py runserver
```

Now open:

- http://127.0.0.1:8000/
- http://127.0.0.1:8000/dashboard/
- http://127.0.0.1:8000/dashboard/login/
- http://127.0.0.1:8000/api/docs/
- http://127.0.0.1:8000/api/schema/

## Production / Render deployment

The app is also deployed on Render:

- https://quickbook-a90h.onrender.com/
- https://quickbook-a90h.onrender.com/dashboard/
- https://quickbook-a90h.onrender.com/api/docs/
- https://quickbook-a90h.onrender.com/api/schema/

## Project folder structure

```text
QuickBook/
├── accounts/
├── bookings/
├── config/
├── dashboard/
├── events/
├── referrals/
├── .gitignore
├── .env.example
├── manage.py
├── README.md
├── requirements.txt
├── render.yaml
├── db.sqlite3
└── staticfiles/
```
Website Sections
Homepage
<img width="1799" height="951" alt="image" src="https://github.com/user-attachments/assets/93f1d4f3-9748-4a5a-87a7-5abb7ecd2503" />

## API overview

All protected API endpoints require an `Authorization: Token <token>` header.

### Authentication
- `POST /api/auth/register/`
- `POST /api/auth/login/`
- `POST /api/auth/logout/`

### Events
- `GET /api/events/`
- `GET /api/events/<id>/`

### Bookings
- `GET /api/bookings/`
- `POST /api/bookings/`
- `POST /api/bookings/<id>/cancel/`

### Referrals
- `GET /api/referrals/<user_id>/tree/`
- `GET /api/referrals/<user_id>/root/`
- `GET /api/referrals/<user_id>/stats/`

## Demo data

If you want some sample data to test the app:

```bash
python manage.py seed_demo
```

This creates example vendors, events, bookings, and staff data.

## Running tests

```bash
python manage.py test
```

## Environment configuration

Create a `.env` file locally and set your environment variables:

```env
DJANGO_SECRET_KEY=your-secret-key
DEBUG=True
ALLOWED_HOSTS=localhost,127.0.0.1
DATABASE_URL=sqlite:////db.sqlite3
CSRF_TRUSTED_ORIGINS=http://localhost:8000,http://127.0.0.1:8000
SECURE_SSL_REDIRECT=False
```


## Security notes

- keep `DEBUG=False` in production
- never expose secrets in the repository
- restrict `ALLOWED_HOSTS`
- use HTTPS on production deployments
- store credentials in environment variables, not in code

## Limitations

- main focus is backend logic and API structure
- no advanced payment gateway integration yet
- no email verification or password reset flow
- no full frontend app is included

## Future improvements

- payment integration
- email verification
- admin analytics dashboard
- stronger referral reporting
- improved frontend UX



