""" This file initializes Celery and connects it to Django """


import os
from celery import Celery
from celery.schedules import crontab


# Sets the environment variable so Django knows which settings module to load.

# Set default Django settings module for Celery
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'Blog_App.settings')

# Create Celery app instance
app = Celery('Blog_App')

# Configures/wires Django’s settings into Celery.
# namespace='CELERY' means all celery-related settings in Django will have 'CELERY_' prefix
app.config_from_object('django.conf:settings', namespace='CELERY')

# Celery will auto-discover tasks.py in each Django app
app.autodiscover_tasks()


# Debug task for testing
@app.task(bind=True, ignore_result=True)   
# ignore_result=True : Tells Celery not to store the result of this task

def debug_task(self):
    """Simple debug task to test if Celery is working"""
    print(f'Request: {self.request!r}')