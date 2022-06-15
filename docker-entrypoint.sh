#!/bin/bash
python3 /app/manage.py migrate --noinput
python3 /app/manage.py bootstrap
python3 /app/manage.py runserver
