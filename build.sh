#!/usr/bin/env bash
# Build script for Render

set -o errexit

python manage.py collectstatic --noinput
python manage.py migrate
