#!/bin/bash
set -e

# Run database migrations
echo "Running database migrations..."
flask db upgrade

# Run database seeding if the database is new/empty
# (Optional: the user can manually run flask seed-db if needed,
# or we can check if database is empty. For safety, we just run migrations).

# Start the application
echo "Starting Gunicorn server..."
exec gunicorn -w 2 -b 0.0.0.0:5000 "app:create_app()"
