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
import random
import string
import re
import logging
from datetime import datetime

from flask import Blueprint, request, make_response
from flask import current_app

from checks import *
from app import db

api = Blueprint('api', __name__)

def token_generator():
    '''
    Generate an user token string. 8 alfanumeric characters.
    '''
    return ''.join(random.choice(string.ascii_uppercase + string.digits)
                   for x in range(8))

@api.route('/register/', methods=['POST'])
def post_register():
    '''
    Receives a registration petition. It might require an additional captcha
    field in some cases. On success, it returns status 200 and sends an
    sms code to the tlf nº of the user.

    Example request:
    POST /register
    {
        "first_name": "Fulanito",
        "last_name": "de tal",
        "email": "email@example.com",
        "tlf": "+34666666666",
        "age": 18,
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
        ['tlf', lambda x: str_constraint(
            x, rx_pattern=current_app.config.get('ALLOWED_TLF_NUMS_RX', None))],
        ['age', lambda x: int_constraint(x, 18)],
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
        ip=request.remote_addr,
        first_name=data["first_name"],
        last_name=data["last_name"],
        email=data["first_name"],
        tlf=data["tlf"],
        age=data["age"],
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
