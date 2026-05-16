# Batchit Backend API

This is the backend service for the Batchit collaborative bulk purchasing platform.

## Features
- User authentication and management.
- Provider profile management.
- Product catalog listings.
- Collaborative batch creation and participation.
- Subscription management.

## Setup
1. Clone the repository.
2. Create and activate a virtual environment.
3. Install dependencies: `pip install -r requirements.txt`
4. Set up the database (PostgreSQL recommended).
5. Apply migrations: `python manage.py migrate`
6. Run the server: `python manage.py runserver`

## API Documentation
The API documentation is available via Swagger at `/api/swagger/`.
