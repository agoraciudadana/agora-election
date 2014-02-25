import os
ROOT_PATH = os.path.dirname(__file__)

### Celery settings

BROKER_URL = 'amqp://'
CELERY_RESULT_BACKEND = 'amqp://'

CELERY_TASK_SERIALIZER = 'json'
CELERY_RESULT_SERIALIZER = 'json'
CELERY_ACCEPT_CONTENT=['json']
CELERY_TIMEZONE = 'Europe/Madrid'
CELERY_ENABLE_UTC = True

if os.path.isfile(os.path.join(ROOT_PATH, "custom_settings.py")):
    from custom_settings import *


