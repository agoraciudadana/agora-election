import os
import re
import json
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

# Method to serialize the critical paths (like "mark as voted" or "create
# voting booth token"). You can either use:
# - "ROWLOCK" which locks only the affected rows (new)
# - "SERIALIZED" which makes all critical path transactions serialized (slower,
#   more tested though)
SERIALIZATION_MODE = "ROWLOCK"

# number of retries when SERIALIZATION_MODE is "SERIALIZED". Ignored otherwise.
MAX_NUM_SERIALIZED_RETRIES = 5

# checks pipeline for sending an sms, you can modify and tune it at will
REGISTER_CHECKS_PIPELINE = (
    ("checks.register_request", None),
    ("checks.check_tlf_has_not_voted", None),
    ("checks.check_dni_has_not_voted", None),
    ("checks.check_tlf_whitelisted", None),
    ("checks.check_ip_whitelisted", None),
    ("checks.check_ip_blacklisted", None),
    ("checks.check_tlf_blacklisted", None),
    ("checks.check_ip_total_unconfirmed_requests_max", dict(total_max=30)),
    ("checks.check_ip_total_max", dict(total_max=8)),
    ("checks.check_tlf_total_max", dict(total_max=7)),
    ("checks.check_tlf_day_max", dict(day_max=5)),
    ("checks.check_tlf_hour_max", dict(hour_max=3)),
    ("checks.check_tlf_expire_max", None),
    ("checks.generate_token", dict(land_line_rx=re.compile("^\+34[89]"))),
    ("checks.send_sms_pipe", None),
)

# example checks pipeline for id-num authentication
'''
REGISTER_CHECKS_PIPELINE = (
    ("checks.register_request", None),
    ("checks.check_ip_whitelisted", None),
    ("checks.check_ip_blacklisted", None),
    ("checks.check_ip_total_unconfirmed_requests_max", dict(total_max=30)),
    ("checks.check_ip_total_max", dict(total_max=3)),
    ("checks.check_minshu_census", dict(
        base_url="http://example.com",
        minshu_user="web",
        minshu_pass="pass"
    )),
    ('checks.return_vote_hmac', None),
)
'''


# example checks pipeline to check against a small census
'''

REGISTER_CHECKS_PIPELINE = (
    ("checks.register_request", None),
    ("checks.check_tlf_has_not_voted", None),
    ("checks.check_dni_has_not_voted", None),
    ("checks.check_tlf_expire_max", None),
    ("checks.check_tlf_whitelisted", None),
    ("checks.check_ip_whitelisted", None),
    ("checks.check_ip_blacklisted", None),
    ("checks.check_tlf_blacklisted", None),
    ("checks.check_ip_total_unconfirmed_requests_max", dict(total_max=30)),
    ("checks.check_ip_total_max", dict(total_max=8)),
    ("checks.check_tlf_total_max", dict(total_max=7)),
    ("checks.check_tlf_day_max", dict(day_max=5)),
    ("checks.check_tlf_hour_max", dict(hour_max=3)),
    ("checks.check_tlf_expire_max", None),
    ("checks.check_id_in_csv_census", None),
    ("checks.generate_token", dict(land_line_rx=re.compile("^\+34[89]"))),
    ("checks.send_sms_pipe", None),
)

# NOTE: that check_id_in_csv_census depends on the following var:
from toolbox import read_csv_to_dicts
CSV_CENSUS = read_csv_to_dicts("census.csv")
'''


# this pipeline is used when receiving a vote. It should check that the vote is
# alright and pass if everything is ok.
# Functions in the pipeline receive as the data argument the POST request sent
# to POST /notify_vote/
NOTIFY_VOTE_PIPELINE = (
    ("checks.check_id_auth", None),
    ("checks.mark_id_authenticated", None),
)

# pipeline for minshu integration
'''
NOTIFY_VOTE_PIPELINE = (
    ("checks.check_id_auth", None),
    ("checks.mark_voted_in_minshu", dict(
        base_url="http://example.com",
        minshu_user="web",
        minshu_pass="pass"
    )),
    ("checks.mark_id_authenticated", None),
)
'''

# timeframe within the SMS message should either be sent or we should give up
# sending a specific SMS. it's also used so that an user have to wait
# SMS_EXPIRE_SECS to send the next sms message
SMS_EXPIRE_SECS = 120

# format the sms message
SMS_MESSAGE = "%(server_name)s: your token is: %(token)s"

# number of guesses for one token
MAX_TOKEN_GUESSES = 3

# timeframe within which a token is said to be valid
SMS_TOKEN_EXPIRE_SECS = 60*10

AGORA_SHARED_SECRET_KEY = "<shared key>"

########### data

# list of static pages, which should be .json files available in the current
# directory. Example:
#STATIC_PAGES = [
    #{
        #'title': 'Preguntas frecuentes',
        #'name': 'faq',
        #'path': 'static/pages/faq.html'
    #},
    #{
        #'title': 'Autoridades de votación',
        #'name': 'authorities',
        #'path': 'static/pages/authorities.html'
    #}
#]
STATIC_PAGES = []

AGORA_ELECTION_DATA_URL = 'https://local.dev/api/v1/election/115/'

# if the url above needs http auth:
#AGORA_ELECTION_DATA_BASIC_AUTH = ("foo", "pass")
AGORA_ELECTION_DATA_BASIC_AUTH = None

# AUTH_METHOD posibilities:
# - "sms"
# - "id-num"
# - "id-photo"
AUTH_METHOD = "sms"

# in years
MIN_AGE = "16"

SHOW_CHECK_RECEIVE_UPDATES = True

SHOW_EMAIL = True

SHOW_POSTAL_CODE = True

AGORA_ELECTION_DATA = dict(
    parent_site=dict(
        name="www.example.com",
        url="//www.example.com",
    ),
    subtitle="This is a text that makes you look good",
    url="https://local.dev/edulix/hola/election/hola5/vote",
    start_voting="20 marzo, 10:00",
    end_voting="27 marzo, 10:00",
    num_votes="0",
    candidates="not-primary",
    primary_mode="",
    tlf_no_rx=ALLOWED_TLF_NUMS_RX,
    static_pages=STATIC_PAGES,
    contact=dict(
        email="agora@example.com",
        twitter_username="example"
    ),
    tos=dict(
        title="He leído y acepto las condiciones",
        text="Lorem ipsum"
    ),
    auth_method=AUTH_METHOD,
    min_age=MIN_AGE,
    show_email=SHOW_EMAIL,
    show_check_receive_updates=SHOW_CHECK_RECEIVE_UPDATES,
    show_postal_code=SHOW_POSTAL_CODE,
)

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
# Voice only (works in esendex): The default language to use for all Voice SMS
# messages in this request. Currently supports: en-GB (English UK),
# en-AU(English-Australian), fr-FR (French), es-ES (Spanish) and de-DE (German).
SMS_VOICE_LANG_CODE = 'es-ES'

########### mail

# These are the default
#MAIL_SERVER  = "localhost"
#MAIL_PORT = 25
#MAIL_DEBUG =~ app.debug
#MAIL_USE_TLS = False
#MAIL_USE_SSL = False
#MAIL_USERNAME = None
#MAIL_PASSWORD = None
MAIL_DEFAULT_SENDER = "agora@example.com"

STATIC_PATH = "/static"

# either remote_addr or a specific header
REAL_IP_GETTER = "remote_addr"

# Insert here custom css styles that you might want to override defaults
CUSTOM_CSS_STYLE = ""

# Insert here any custom javascript that you might need
CUSTOM_JAVASCRIPT = ""

if os.path.isfile(os.path.join(ROOT_PATH, "custom_settings.py")):
    from custom_settings import *
else:
    logging.warn("custom_settings.py not being loaded")
