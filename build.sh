#!/usr/bin/env bash
# exit on error
set -o errexit

pip install -r requirements.txt

python manage.py collectstatic --no-input
python manage.py migrate

# Automatically ensure superuser admin exists on Render
python -c "
import django, os
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'Core.settings')
django.setup()
from django.contrib.auth import get_user_model
User = get_user_model()
if not User.objects.filter(username='admin').exists():
    User.objects.create_superuser('admin', 'admin@example.com', 'admin123')
    print('Superuser created successfully')
else:
    u = User.objects.get(username='admin')
    u.set_password('admin123')
    u.is_superuser = True
    u.is_staff = True
    u.save()
    print('Superuser updated successfully')
"