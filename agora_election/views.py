# -*- coding: utf-8 -*-
#
# This file is part of agora-election.
# Copyright (C) 2013  Eduardo Robles Elvira <edulix AT agoravoting DOT com>

# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU Affero General Public License for more details.
#
# You should have received a copy of the GNU Affero General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.

import json

from flask import Blueprint, request, make_response, render_template, url_for
from flask.ext.mail import Message as MailMessage
from flask.ext.babel import gettext, ngettext
from flask import current_app
from jinja2 import Markup

from checks import *
from app import db, app_mail
from crypto import constant_time_compare, salted_hmac, get_random_string

api = Blueprint('api', __name__)
index = Blueprint('index', __name__)

def token_generator():
    '''
    Generate an user token string. 8 alfanumeric characters. We do not allow
    confusing characters: 0,O,I,1
    '''
    return get_random_string(8, 'ABCDEFGHJKLMNPQRSTUVWXYZ23456789')

@api.route('/register/', methods=['POST'])
def post_register():
    '''
    Receives a registration petition. It might require an additional captcha
    field in some cases. On success, it returns status 200 and sends an
    sms code to the tlf nº of the user.

    Example request:
    POST /api/v1/register/
    {
        "first_name": "Fulanito",
        "last_name": "de tal",
        "email": "email@example.com",
        "tlf": "+34666666666",
        "postal_code": 41010,
        "receive_updates": true
    }

    Successful response is empty
    '''
    from tasks import send_sms
    from models import Voter, Message

    # first of all, parse input data
    data = request.get_json(force=True, silent=True)
    if data is None:
        return error("invalid json", error_codename="not_json")

    # initial input checking
    input_checks = (
        ['first_name', lambda x: str_constraint(x, 3, 60)],
        ['last_name', lambda x: str_constraint(x, 3, 100)],
        ['email', email_constraint],
        ['postal_code', lambda x: int_constraint(x, 1, 100000)],
        ['tlf', lambda x: str_constraint(
            x, rx_pattern=current_app.config.get('ALLOWED_TLF_NUMS_RX', None))],
        ['receive_updates', lambda x: isinstance(x, bool)],
    )
    check_status = constraints_checker(input_checks, data)
    if  check_status is not True:
        return check_status

    # do a deeper input check: check that the ip is not blacklisted, or that
    # the tlf has already voted..
    check_status = check_registration_pipeline(request.remote_addr, data)
    if  check_status is not True:
        return check_status

    # disable older registration attempts for this tlf
    curr_eid = current_app.config.get("CURRENT_ELECTION_ID", 0)
    old_voters = db.session.query(Voter)\
        .filter(Voter.election_id == curr_eid,
                Voter.tlf == data["tlf"],
                Voter.is_active == True)
    for ov in old_voters:
        ov.is_active = False
        db.session.add(ov)

    # create the message to be sent
    token = token_generator()
    msg = Message(
        tlf=data["tlf"],
        ip=request.remote_addr,
        lang_code=current_app.config.get("BABEL_DEFAULT_LOCALE", "en"),
        token=token,
        status=Message.STATUS_QUEUED,
    )

    # create voter and send sms
    voter = Voter(
        election_id=curr_eid,
        ip=request.remote_addr,
        first_name=data["first_name"],
        last_name=data["last_name"],
        email=data["first_name"],
        tlf=data["tlf"],
        postal_code=data["tlf"],
        receive_mail_updates=data["receive_updates"],
        lang_code=msg.lang_code,
        status=Voter.STATUS_CREATED,
        message=msg,
        is_active=True,
    )

    db.session.add(voter)
    db.session.add(msg)
    db.session.commit()

    send_sms.apply_async(kwargs=dict(msg_id=msg.id),
        countdown=current_app.config.get('SMS_DELAY', 1),
        expires=current_app.config.get('SMS_EXPIRE_SECS', 120))


    return make_response("", 200)

def set_serializable():
    # if using postgres, then we check concurrency
    if "postgres" in current_app.config.get("SQLALCHEMY_DATABASE_URI", ""):
        import psycopg2
        conn = db.session.bind.engine.connect().connection.connection
        conn.set_isolation_level(
            psycopg2.extensions.ISOLATION_LEVEL_SERIALIZABLE)

def unset_serializable():
    # if using postgres, then we check concurrency
    if "postgres" in current_app.config.get("SQLALCHEMY_DATABASE_URI", ""):
        import psycopg2
        conn = db.session.bind.engine.connect().connection.connection
        conn.set_isolation_level(
            psycopg2.extensions.ISOLATION_LEVEL_READ_COMMITTED)

@api.route('/sms_auth/', methods=['POST'])
def post_sms_auth():
    '''
    Receives an sms authentication.

    Example request:
    POST /api/v1/sms_auth/
    {
        "tlf": "+34666666666",
        "token": "AA4TL219",
    }

    Successful response:
    {
        "message": "<auth_date_timestamp>#<voter_id>",
        "sha1_hmac": "<sha1 hash>",
    }
    '''
    from tasks import send_sms
    from models import Voter, Message

    # first of all, parse input data
    data = request.get_json(force=True, silent=True)
    if data is None:
        return error("invalid json", error_codename="not_json")

    # initial input checking
    input_checks = (
        ['tlf', lambda x: str_constraint(
            x, rx_pattern=current_app.config.get('ALLOWED_TLF_NUMS_RX', None))],
        ['token', lambda x: str_constraint(x, rx_pattern="[0-9A-Z]{8}")],
    )
    check_status = constraints_checker(input_checks, data)
    if  check_status is not True:
        return check_status

    # check that voter has not voted
    curr_eid = current_app.config.get("CURRENT_ELECTION_ID", 0)
    set_serializable()
    voters = db.session.query(Voter)\
        .filter(Voter.election_id == curr_eid,
                Voter.tlf == data["tlf"],
                Voter.status == Voter.STATUS_SENT,
                Voter.is_active == True)
    if voters.count() == 0:
        unset_serializable()
        return error("Voter has not any sms", error_codename="sms_notsent")
    voter = voters.first()

    # check token has not too many guesses or has expired
    expire_time = current_app.config.get('SMS_TOKEN_EXPIRE_SECS', 60*10)
    expire_dt = datetime.utcnow() - timedelta(seconds=expire_time)

    if voter.token_guesses >= current_app.config.get("MAX_TOKEN_GUESSES", 5) or\
            voter.message.created <= expire_dt:
        return error("Voter provided invalid token, please try a new one",
                     error_codename="need_new_token")

    # check token
    if not constant_time_compare(data["token"].upper(), voter.message.token):
        voter.token_guesses += 1
        voter.modified = datetime.utcnow()
        db.session.add(voter)
        db.session.commit()
        unset_serializable()
        return error("Voter provided invalid token", error_codename="invalid_token")

    voter.status = Voter.STATUS_AUTHENTICATED
    voter.modified = datetime.utcnow()
    db.session.add(voter)

    # invalidate other voters with same tlf
    for v in voters[1:]:
        v.is_active = False
        db.session.add(v)
    db.session.commit()
    # okey now we have finished the critical serialized path, we can breath now
    unset_serializable()

    message = "%d#%d" % (
        int(datetime.utcnow().timestamp()),
        voter.id
    )
    key = current_app.config.get("AGORA_SHARED_SECRET_KEY", "")

    ret_data = dict(
        message=message,
        sha1_hmac=salted_hmac(key, message, "").hexdigest()
    )
    return make_response(json.dumps(ret_data), 200)


@api.route('/notify_vote/', methods=['POST'])
def post_notify_vote():
    '''
    Receives an authenticated message from agora saying "someone with id XX
    has voted", and we have to mark this voter as voted so that the voter
    cannot vote again.

    Example request:
    POST /api/v1/notify_vote/
    {
        "identifier": "<id>",
        "sha1_hmac": "AA4TL219",
    }

    Successful response: STATUS 200
    '''
    from tasks import send_sms
    from models import Voter, Message

    # first of all, parse input data
    data = request.get_json(force=True, silent=True)
    if data is None:
        return error("invalid json", error_codename="not_json")

    # initial input checking
    input_checks = (
        ['identifier', lambda x: str_constraint(x, rx_pattern="\d{1,12}")],
        ['sha1_hmac', lambda x: str_constraint(x, rx_pattern="[0-9a-z]{40}")],
    )
    check_status = constraints_checker(input_checks, data)
    if  check_status is not True:
        return check_status

    # check that voter has not voted
    curr_eid = current_app.config.get("CURRENT_ELECTION_ID", 0)
    set_serializable()
    voters = db.session.query(Voter)\
        .filter(Voter.election_id == curr_eid,
                Voter.status == Voter.STATUS_AUTHENTICATED,
                Voter.is_active == True,
                Voter.id == int(data['identifier']))
    if voters.count() == 0:
        unset_serializable()
        return error("Invalid identifier", error_codename="invalid_id")
    voter = voters.first()

    # check token
    key = current_app.config.get("AGORA_SHARED_SECRET_KEY", "")
    hmac = salted_hmac(key, data['identifier'], "").hexdigest()
    if not constant_time_compare(data["sha1_hmac"], hmac):
        unset_serializable()
        return error("Invalid hmac", error_codename="invalid_hmac")

    voter.status = Voter.STATUS_VOTED
    voter.modified = datetime.utcnow()
    db.session.add(voter)
    db.session.commit()
    # okey now we have finished the critical serialized path, we can breath now
    unset_serializable()
    return make_response("", 200)


@api.route('/contact/', methods=['POST'])
def post_contact():
    '''
    Receives an contact form that will be sent to our admins.

    Example request:
    POST /api/v1/contact/
    {
        "name": "Pepito Grillo",
        "email": "me@example.com",
        "tlf": "+34666666666",
        "text_body": "message",
    }

    Successful response: STATUS 200
    '''
    from models import Voter, Message

    # first of all, parse input data
    data = request.get_json(force=True, silent=True)
    if data is None:
        return error("invalid json", error_codename="not_json")

    # initial input checking
    input_checks = (
        ['name', lambda x: str_constraint(x, 5, 160)],
        ['body', lambda x: str_constraint(x, 10, 4000)],
        ['email', email_constraint],
        ['tlf', lambda x: len(x) == 0 or str_constraint(
            x, rx_pattern=current_app.config.get('ALLOWED_TLF_NUMS_RX', None))],
    )
    check_status = constraints_checker(input_checks, data)
    if  check_status is not True:
        return check_status

    subject = gettext("[%(site)s] Contact msg from %(name)s",
                       site=current_app.config.get('SERVER_NAME', ''),
                       name=data['name'])
    recipients = [mail_addr
                  for name, mail_addr in current_app.config.get('ADMINS', [])]
    msg = MailMessage(subject=subject,
                      sender=current_app.config.get('MAIL_DEFAULT_SENDER', []),
                      recipients=recipients)
    msg.body = gettext("Message from %(name)s <%(email)s> (tlf %(tlf)s, ip: "
                       "%(ip)s): \n%(body)s",
                       name=data['name'],
                       tlf=data['tlf'],
                       ip=request.remote_addr,
                       email=data['email'],
                       body=data['body'])
    app_mail.send(msg)

    return make_response("", 200)

@index.route('/', methods=['GET'])
def get_index():
    data_str = Markup(json.dumps(
        current_app.config.get('AGORA_ELECTION_DATA', {})
    ))
    static_path = current_app.config.get('STATIC_PATH', '/static')
    return render_template('index.html', data=data_str, static_path=static_path)
