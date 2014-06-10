# -*- coding: utf-8 -*-
#
# This file is part of agora-election.
# Copyright (C) 2013, 2014  Eduardo Robles Elvira <edulix AT agoravoting DOT com>

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
import random
import time
from functools import partial

from flask import Blueprint, request, make_response, render_template, url_for
from flask.ext.mail import Message as MailMessage
from flask.ext.babel import gettext, ngettext
from flask.ext.captcha.models import CaptchaStore
from flask import current_app
from jinja2 import Markup

from sqlalchemy.orm import exc as sa_exc

from toolbox import *
from checks import *
from app import db, app_mail
from crypto import constant_time_compare, salted_hmac, get_random_string, hash_token

api = Blueprint('api', __name__)
index = Blueprint('index', __name__)

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
        "dni": "44055111F",
        "tlf": "+34666666666",
        "captcha_key": "a7b10fa7b10fa7b10fa7b10fa7b10fa7b",
        "captcha_text": "BEEF",
        "postal_code": 41010,
        "receive_updates": true
    }

    Successful response is empty
    '''
    from tasks import send_sms
    from models import Voter, Message
    auth_method = current_app.config.get('AUTH_METHOD', None)

    election = current_app.config.get('AGORA_ELECTION_DATA', '')['election']
    if election['voting_ends_at_date'] is not None:
        return error("voting period ended", error_codename='voting_ended')

    # first of all, parse input data
    data = request.get_json(force=True, silent=True)
    if data is None:
        return error("invalid json", error_codename="not_json")

    # initial input checking
    input_checks = (
        ['first_name', lambda x: str_constraint(x, 3, 60)],
        ['last_name', lambda x: str_constraint(x, 3, 100)],
        ['receive_updates', lambda x: isinstance(x, bool)],
        ['dni', lambda x: dni_constraint(x)],
    )

    if auth_method == 'sms':
        input_checks += (
            ['tlf', lambda x: str_constraint(x, rx_pattern=current_app.config.get('ALLOWED_TLF_NUMS_RX', None))],
        )

    if current_app.config.get('SHOW_EMAIL', None):
        input_checks += (
            ['email', email_constraint],
        )

    if current_app.config.get('SHOW_POSTAL_CODE', None):
        input_checks += (
            ['postal_code', lambda x: int_constraint(x, 1, 100000)],
        )

    if current_app.config.get('REGISTER_SHOWS_CAPTCHA', None):
        input_checks += (
            ['captcha_key', lambda x: str_constraint(x, rx_pattern="[0-9a-z]{40}")],
            ['captcha_text', lambda x: CaptchaStore.validate(data['captcha_key'], x.lower())],
        )
    check_status = constraints_checker(input_checks, data)
    if  check_status is not True:
        return check_status

    # do a deeper input check: check that the ip is not blacklisted, or that
    # the tlf has already voted..
    @serializable_retry
    def critical_path():
        data['ip_addr'] = get_ip(request)
        return execute_pipeline(data,
            current_app.config.get('SMS_CHECKS_PIPELINE', []))

    return critical_path()

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
    if current_app.config.get('AUTH_METHOD', None) != 'sms':
        return error("Invalid auth method", error_codename="unauthorized")

    from tasks import send_sms
    from models import Voter, Message

    election = current_app.config.get('AGORA_ELECTION_DATA', '')['election']
    if election['voting_ends_at_date'] is not None:
        return error("voting period ended", error_codename='voting_ended')

    # first of all, parse input data
    data = request.get_json(force=True, silent=True)
    if data is None:
        return error("invalid json", error_codename="not_json")

    # initial input checking
    input_checks = (
        ['tlf', lambda x: str_constraint(
            x, rx_pattern=current_app.config.get('ALLOWED_TLF_NUMS_RX', None))],
        ['token', lambda x: str_constraint(x, rx_pattern="[0-9A-Z]{8}")],
        ['dni', lambda x: dni_constraint(x)],
    )
    check_status = constraints_checker(input_checks, data)
    if  check_status is not True:
        return check_status

    # check that voter has not voted
    curr_eid = current_app.config.get("CURRENT_ELECTION_ID", 0)
    @serializable_retry
    def critical_path():
        voters = db.session.query(Voter)\
            .filter(Voter.election_id == curr_eid,
                    Voter.tlf == data["tlf"],
                    Voter.dni == data["dni"].upper(),
                    Voter.status == Voter.STATUS_SENT,
                    Voter.is_active == True)
        if voters.count() == 0:
            return error("Voter has not any sms", error_codename="sms_notsent")
        voter = voters.first()

        # check token has not too many guesses or has expired
        expire_time = current_app.config.get('SMS_TOKEN_EXPIRE_SECS', 60*10)
        expire_dt = datetime.utcnow() - timedelta(seconds=expire_time)

        if voter.token_guesses >= current_app.config.get("MAX_TOKEN_GUESSES", 5) or\
                voter.message.created <= expire_dt:
            return error("Voter provided invalid token, please try a new one",
                        error_codename="need_new_token")


        token = data["token"].upper()
        token_hash = hash_token(token)

        # check token
        if not constant_time_compare(token_hash, voter.message.token):
            voter.token_guesses += 1
            voter.modified = datetime.utcnow()
            db.session.add(voter)
            db.session.commit()
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
        return voter
    voter = critical_path()
    if not isinstance(voter, Voter):
        return voter

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

    election = current_app.config.get('AGORA_ELECTION_DATA', '')['election']
    if election['voting_ends_at_date'] is not None:
        return error("voting period ended", error_codename='voting_ended')

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
    @serializable_retry
    def critical_path():
        return execute_pipeline(data,
            current_app.config.get('NOTIFY_VOTE_PIPELINE', []))

    ret = critical_path()
    if ret is not None:
        return ret

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
        ['captcha_key', lambda x: str_constraint(x, rx_pattern="[0-9a-z]{40}")],
        ['captcha_text', lambda x: CaptchaStore.validate(data['captcha_key'], x.lower())],
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
                       ip=get_ip(request),
                       email=data['email'],
                       body=data['body']).encode('ascii', 'ignore')
    app_mail.send(msg)

    return make_response("", 200)
	
@api.route('/upload-dni/', methods=['POST'])
def upload_dni():
    '''
    TODO Receives dni uploads
    '''
    from flask import request, jsonify
    import os
    import uuid

    path = current_app.config.get('DNI_FILE_PATH', '/tmp/aelection-dni/')
    if not os.path.exists(path):
        os.makedirs(path)

    data_file = request.files.get('dni')
    file_name = data_file.filename
    unique_filename = str(uuid.uuid4())
    full_path = os.path.join(path, unique_filename)
    data_file.save(full_path)
    file_size = os.path.getsize(full_path)

    return jsonify(name=unique_filename, size=file_size)

@index.route('/', methods=['GET'])
def get_index():
    '''
    Returns the index page
    '''
    data_str = current_app.config.get('AGORA_ELECTION_DATA_STR', '')
    static_path = current_app.config.get('STATIC_PATH', '/static')
    return render_template('index.html', data=data_str, static_path=static_path)
