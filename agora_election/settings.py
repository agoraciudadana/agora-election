import os
import re
import logging
ROOT_PATH = os.path.dirname(__file__)

########### agora-election

SITE_NAME = "Agora-Election"

# change for each election
CURRENT_ELECTION_ID = 0

ADMINS = (
    ('Bob Marley', 'bob@example.com'),
)

# delay tasks if needed. sqlite needs it
TASKS_DELAY = 1

# registration will only allow numbers with this format
ALLOWED_TLF_NUMS_RX = "^\+34[67]\\d{8}$"

# checks pipeline for sending an sms, you can modify and tune it at will
SMS_CHECKS_PIPELINE = (
    ("checks.check_has_not_voted", None),
    ("checks.check_tlf_whitelisted", None),
    ("checks.check_ip_whitelisted", None),
    ("checks.check_blacklisted", None),
    ("checks.check_ip_total_max", dict(total_max=8)),
    ("checks.check_tlf_total_max", dict(total_max=7)),
    ("checks.check_tlf_day_max", dict(day_max=5)),
    ("checks.check_tlf_hour_max", dict(hour_max=3)),
    ("checks.check_tlf_expire_max", None),
)

# timeframe within the SMS message should either be sent or we should give up
# sending a specific SMS. it's also used so that an user have to wait
# SMS_EXPIRE_SECS to send the next sms message
SMS_EXPIRE_SECS = 120

# format the sms message
SMS_MESSAGE = "%(server_name)s: your token is: %(token)s"

# number of guesses for one token
MAX_TOKEN_GUESSES = 5

# timeframe within which a token is said to be valid
SMS_TOKEN_EXPIRE_SECS = 60*10

########### flask

DEBUG = False

TESTING = False

SESSION_COOKIE_SECURE = True

USE_X_SENDFILE = False

SERVER_NAME = "localhost"

SECRET_KEY = "<change this>"

BABEL_DEFAULT_LOCALE = 'en'

########### settings

SQLALCHEMY_DATABASE_URI = ''

########### celery

BROKER_URL = 'amqp://'
CELERY_RESULT_BACKEND = 'amqp://'

CELERY_TASK_SERIALIZER = 'json'
CELERY_RESULT_SERIALIZER = 'json'
CELERY_ACCEPT_CONTENT=['json']
CELERY_TIMEZONE = 'Europe/Madrid'
CELERY_ENABLE_UTC = True

########### sms provider

SMS_PROVIDER = 'altiria'
SMS_DOMAIN_ID = 'comercial'
SMS_LOGIN = ''
SMS_PASSWORD = ''
SMS_URL = 'http://www.altiria.net/api/http'
SMS_SENDER_ID = ''


if os.path.isfile(os.path.join(ROOT_PATH, "custom_settings.py")):
    from custom_settings import *
else:
    logging.warn("custom_settings.py not being loaded")
