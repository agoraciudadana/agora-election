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
from flask import current_app
from jinja2 import Markup

from checks import *
from app import db
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
        "postal_code": "41010",
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
    if not constant_time_compare(data["token"], voter.message.token):
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

@index.route('/', methods=['GET'])
def get_index():
    data = current_app.config.get("AGORA_ELECTION_DATA", dict())
    return render_template('index.html', data=Markup(json.dumps(data)))
