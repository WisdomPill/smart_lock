#!/bin/sh

# Apply database migrations
echo "Apply database migrations"
python3 manage.py migrate

# Load data into the server
#echo "Load data into the server"
#python3 manage.py loaddata default_data.json

# Start server
echo "Starting server"
python3 manage.py runserver 0.0.0.0:8000
