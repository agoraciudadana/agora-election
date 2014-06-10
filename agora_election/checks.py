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
import re
import logging
from datetime import datetime, timedelta

from flask import Blueprint, request, make_response
from flask import current_app

RET_PIPE_CONTINUE = 0
RET_PIPE_SUCCESS = 1
EMAIL_RX = re.compile(
    r"(^[-!#$%&'*+/=?^_`{}|~0-9A-Z]+(\.[-!#$%&'*+/=?^_`{}|~0-9A-Z]+)*"  # dot-atom
    # quoted-string, see also http://tools.ietf.org/html/rfc2822#section-3.2.5
    r'|^"([\001-\010\013\014\016-\037!#-\[\]-\177]|\\[\001-\011\013\014\016-\177])*"'
    r')@((?:[A-Z0-9](?:[A-Z0-9-]{0,61}[A-Z0-9])?\.)+(?:[A-Z]{2,6}\.?|[A-Z0-9-]{2,}\.?)$)'  # domain
    r'|\[(25[0-5]|2[0-4]\d|[0-1]?\d?\d)(\.(25[0-5]|2[0-4]\d|[0-1]?\d?\d)){3}\]$', re.IGNORECASE)  # literal form, ipv4 address (SMTP 4.1.3)

DNI_RX = re.compile("[A-Z]?[0-9]{7,8}[A-Z]", re.IGNORECASE)
LETTER_RX = re.compile("[A-Z]", re.IGNORECASE)

def error(message="", status=400, field=None, error_codename=None):
    '''
    Returns an error message
    '''

    data = dict(message=message, field=field, error_codename=error_codename)
    return make_response(json.dumps(data), status)

def constraints_checker(checks, data):
    '''
    Checks a dict for contraints and return an error on failure
    '''
    if not isinstance(data, dict):
        return error("data is not an dictionary", error_codename="not_a_dict")

    keys = []
    for key, checker in checks:
        if key not in keys:
            keys.append(key)
        if key not in data or not checker(data[key]):
            return error("Invalid input for '%s'" % key, field=key,
                         error_codename="invalid_key_constraint")

    if set(keys) != set(data.keys()):
        unknown_keys = str(set(data.keys()) - set(keys))
        error_str =  "Invalid keys appear in input data: %s" % unknown_keys
        return error(error_str, error_codename="unknown_keys")

    return True

def str_constraint(val, min_length=None, max_length=None, rx_pattern=None):
    '''
    Check that the input value is a string with some constraints
    '''
    if not isinstance(val, str):
        return False
    if min_length is not None and len(val) < min_length:
        return False
    if max_length is not None and len(val) > max_length:
        return False
    if rx_pattern is not None and not re.match(rx_pattern, val):
        return False
    return True

def email_constraint(val):
    '''
    check that the input is an email string
    '''
    if not isinstance(val, str):
        return False
    return EMAIL_RX.match(val)

def dni_constraint(val):
    '''
    check that the input is a valid dni
    '''
    if not isinstance(val, str):
        return False

    val2 = val.upper()
    if not DNI_RX.match(val2):
        return False

    if LETTER_RX.match(val2[0]):
        nie_letter = val2[0]
        val2 = val2[1:]
        if nie_letter == 'Y':
            val2 = "1" + val2
        elif nie_letter == 'Z':
            val2 = "2" + val2

    mod_letters = 'TRWAGMYFPDXBNJZSQVHLCKE'
    digits = val2[:-1]
    letter = val2[-1].upper()

    expected = mod_letters[int(digits) % 23]

    return letter == expected

def int_constraint(val, min_val=None, max_val=None):
    '''
    Checks that the value is an integer with some optional constraints.
    '''
    if not isinstance(val, int):
        return False
    if min_val is not None and val < min_val:
        return False
    if max_val is not None and val > max_val:
        return False
    return True

def check_has_not_voted(data):
    '''
    check that tlf should have not voted
    '''
    from app import db
    from models import Voter

    ip_addr = data['ip_addr']
    curr_eid = current_app.config.get("CURRENT_ELECTION_ID", 0)

    voter = db.session.query(Voter)\
        .filter(Voter.election_id == curr_eid,
                Voter.tlf == data["tlf"],
                Voter.status == Voter.STATUS_VOTED,
                Voter.is_active == True).first()
    if voter is not None:
        return error("Voter already voted", field="tlf",
                     error_codename="already_voted")
    return RET_PIPE_CONTINUE


def check_dni_has_not_voted(data):
    '''
    check that dni should have not voted
    '''
    from app import db
    from models import Voter

    ip_addr = data['ip_addr']
    curr_eid = current_app.config.get("CURRENT_ELECTION_ID", 0)

    voter = db.session.query(Voter)\
        .filter(Voter.election_id == curr_eid,
                Voter.dni == data["dni"].upper(),
                Voter.status == Voter.STATUS_VOTED,
                Voter.is_active == True).first()
    if voter is not None:
        return error("Voter already voted", field="dni",
                     error_codename="already_voted")

    return RET_PIPE_CONTINUE

def check_tlf_whitelisted(data):
    '''
    If tlf is whitelisted, accept
    '''
    from app import db
    from models import ColorList

    ip_addr = data['ip_addr']
    item = db.session.query(ColorList)\
        .filter(ColorList.key == ColorList.KEY_TLF,
                ColorList.value == data["tlf"]).first()
    if item is not None:
        if item.action == ColorList.ACTION_WHITELIST:
            return RET_PIPE_SUCCESS
        else:
            data["tlf_blacklisted"] = True
    else:
        data["tlf_blacklisted"] = False
    return RET_PIPE_CONTINUE

def check_ip_whitelisted(data):
    '''
    If ip is whitelisted, then do not blacklist by ip in the following checkers
    '''
    from app import db
    from models import ColorList

    ip_addr = data['ip_addr']
    items = db.session.query(ColorList)\
        .filter(ColorList.key == ColorList.KEY_IP,
                ColorList.value == ip_addr)

    for item in items:
        if item.action == ColorList.ACTION_WHITELIST:
            return RET_PIPE_SUCCESS

    return RET_PIPE_CONTINUE

def check_ip_blacklisted(data):
    '''
    check if tlf is blacklisted
    '''
    from app import db
    from models import ColorList

    ip_addr = data['ip_addr']
    # optimization: if we have already gone through the whitelisting checking
    # we don't have do new queries
    if 'ip_blacklisted' in data:
        if data['ip_blacklisted'] is True:
            return error("Blacklisted", error_codename="blacklisted")

        return RET_PIPE_CONTINUE

    item = db.session.query(ColorList)\
        .filter(ColorList.key == ColorList.KEY_IP,
                ColorList.action == ColorList.ACTION_BLACKLIST,
                ColorList.value == ip_addr).first()
    if item is not None:
        return error("Blacklisted", error_codename="blacklisted")

    return RET_PIPE_CONTINUE

def check_tlf_blacklisted(data):
    '''
    check if tlf is blacklisted
    '''
    from app import db
    from models import ColorList

    # optimization: if we have already gone through the whitelisting checking
    # we don't have do new queries
    if 'tlf_blacklisted' in data:
        if data['tlf_blacklisted']:
            return error("Blacklisted", error_codename="blacklisted")

        return RET_PIPE_CONTINUE

    item = db.session.query(ColorList)\
        .filter(ColorList.key == ColorList.KEY_TLF,
                ColorList.action == ColorList.ACTION_BLACKLIST,
                ColorList.value == data["tlf"]).first()
    if item is not None:
        return error("Blacklisted", error_codename="blacklisted")

    return RET_PIPE_CONTINUE

def check_tlf_total_max(data, total_max):
    '''
    if tlf has been sent >= MAX_SMS_LIMIT failed-sms in total->blacklist, error
    '''
    from app import db
    from models import ColorList, Message

    ip_addr = data['ip_addr']
    item = db.session.query(Message)\
        .filter(Message.tlf == data["tlf"],
                Message.authenticated == False,
                Message.status == Message.STATUS_SENT).count()
    if item >= total_max:
        logging.warn("check_tlf_total_max: blacklisting")
        cl = ColorList(action=ColorList.ACTION_BLACKLIST,
                       key=ColorList.KEY_TLF,
                       value = data["tlf"])
        cl2 = ColorList(action=ColorList.ACTION_BLACKLIST,
                       key=ColorList.KEY_IP,
                       value = ip_addr)
        db.session.add(cl)
        db.session.add(cl2)
        db.session.commit()
        return error("Blacklisted", error_codename="blacklisted")
    return RET_PIPE_CONTINUE

def check_tlf_day_max(data, day_max):
    '''
    if tlf has been sent >= MAX_DAY_SMS_LIMIT failed-sms last day-> error
    '''
    from app import db
    from models import Message

    ip_addr = data['ip_addr']
    item = db.session.query(Message)\
        .filter(Message.tlf == data["tlf"],
                Message.authenticated == False,
                Message.status == Message.STATUS_SENT,
                Message.modified >= (datetime.utcnow() - timedelta(days=1))
                ).count()
    if item >= day_max:
        return error("Too many messages sent in a day", error_codename="wait_day")
    return RET_PIPE_CONTINUE

def check_tlf_hour_max(data, hour_max):
    '''
    if tlf has been sent >= MAX_SMS_LIMIT failed-sms last hour-> error
    '''
    from app import db
    from models import Message

    ip_addr = data['ip_addr']
    item = db.session.query(Message)\
        .filter(Message.tlf == data["tlf"],
                Message.authenticated == False,
                Message.status == Message.STATUS_SENT,
                Message.modified >= (datetime.utcnow() - timedelta(hours=1))
                ).count()
    if item >= hour_max:
        return error("Too many messages sent in an hour", error_codename="wait_hour")
    return RET_PIPE_CONTINUE

def check_tlf_expire_max(data):
    '''
    if tlf has been sent an sms in < SMS_EXPIRE_SECS, error
    '''
    from app import db
    from models import Message

    ip_addr = data['ip_addr']
    secs = current_app.config.get('SMS_EXPIRE_SECS', 120)
    item = db.session.query(Message)\
        .filter(Message.tlf == data["tlf"],
                Message.authenticated == False,
                Message.status == Message.STATUS_SENT,
                Message.modified >= (datetime.utcnow() - timedelta(seconds=secs))
                ).first()
    if item is not None:
        return error("Please wait until your sms arrives", error_codename="wait_expire")
    return RET_PIPE_CONTINUE

def check_ip_total_max(data, total_max):
    '''
    if tlf has been sent an sms in < SMS_EXPIRE_SECS, error
    '''
    from app import db
    from models import ColorList, Message

    ip_addr = data['ip_addr']
    item = db.session.query(Message)\
        .filter(Message.ip == ip_addr,
                Message.authenticated == False,
                Message.status == Message.STATUS_SENT).count()
    if item >= total_max:
        logging.warn("check_ip_total_max: blacklisting")
        cl = ColorList(action=ColorList.ACTION_BLACKLIST,
                       key=ColorList.KEY_IP,
                       value = ip_addr)
        db.session.add(cl)
        db.session.commit()
        return error("Blacklisted", error_codename="blacklisted")
    return RET_PIPE_CONTINUE

def send_sms_pipe(data):
    '''
    check that the ip is not blacklisted, or that the tlf has already voted,
    and finally set the return value
    '''
    from app import db
    from models import Voter, Message
    from toolbox import hash_token, token_generator
    from tasks import send_sms

    ip_addr = data['ip_addr']

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
    token_hash = hash_token(token)
    msg = Message(
        tlf=data["tlf"],
        ip=ip_addr,
        lang_code=current_app.config.get("BABEL_DEFAULT_LOCALE", "en"),
        token=token_hash,
        status=Message.STATUS_QUEUED,
    )

    # create voter and send sms
    voter = Voter(
        election_id=curr_eid,
        ip=ip_addr,
        first_name=data["first_name"],
        last_name=data["last_name"],
        email=data.get("email", ""),
        tlf=data["tlf"],
        postal_code=data.get("postal_code", ""),
        receive_mail_updates=data["receive_updates"],
        lang_code=msg.lang_code,
        status=Voter.STATUS_CREATED,
        message=msg,
        is_active=True,
        dni=data["dni"].upper(),
    )

    db.session.add(voter)
    db.session.add(msg)
    db.session.commit()

    send_sms.apply_async(kwargs=dict(msg_id=msg.id, token=token),
        countdown=current_app.config.get('SMS_DELAY', 1),
        expires=current_app.config.get('SMS_EXPIRE_SECS', 120))

    return make_response("", 200)

def check_minshu_census(data, **kwargs):
    '''
    Checks in minshu census that no user with the same ID has voted
    '''
    import requests
    from crypto import hash_str

    dni = data["dni"].upper()
    curr_eid = current_app.config.get("CURRENT_ELECTION_ID", 0)

    url = "%(base_url)s/api/v1/voter/%(id)s" % dict(
        base_url= kwargs["base_url"],
        id = hash_str(dni)
    )
    headers = {}

    # TODO: use authentication
    r = requests.get(url, headers=headers)
    # DNI is new
    if r.status_code == 404:
        return RET_PIPE_CONTINUE
    elif r.status_code == 200:
        # TODO: check the extra
        return error("Already voted", field="dni",
                     error_codename="already_voted")
    else:
        return error("Service unavailable", error_codename="unavailable")

def return_vote_hmac(data):
    '''
    In three steps auth methods (id-num, id-photo), return directly the hmac
    to vote as there's no third-step verification.
    '''
    from crypto import salted_hmac, get_random_string
    from app import db
    from models import Voter
    from crypto import hash_str

    dni = data["dni"].upper()
    ip_addr = data['ip_addr']

    curr_eid = current_app.config.get("CURRENT_ELECTION_ID", 0)
    # create voter
    voter = Voter(
        election_id=curr_eid,
        ip=ip_addr,
        first_name="-",
        last_name="-",
        email="-",
        tlf="-",
        postal_code=data.get("postal_code", ""),
        receive_mail_updates=data["receive_updates"],
        lang_code=current_app.config.get("BABEL_DEFAULT_LOCALE", "en"),
        status=Voter.STATUS_AUTHENTICATED,
        modified = datetime.utcnow(),
        message=None,
        is_active=True,
        dni=hash_str(dni),
    )

    db.session.add(voter)
    db.session.commit()

    data['identifier'] = voter.id

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

#### notify-pipes

def check_id_auth(data):
    from app import db
    from models import Voter
    from crypto import salted_hmac, constant_time_compare

    curr_eid = current_app.config.get("CURRENT_ELECTION_ID", 0)
    voters = db.session.query(Voter)\
        .filter(Voter.election_id == curr_eid,
                Voter.status == Voter.STATUS_AUTHENTICATED,
                Voter.is_active == True,
                Voter.id == int(data['identifier']))
    if voters.count() == 0:
        return error("Invalid identifier", error_codename="invalid_id")

    # check token
    key = current_app.config.get("AGORA_SHARED_SECRET_KEY", "")
    hmac = salted_hmac(key, data['identifier'], "").hexdigest()
    if not constant_time_compare(data["sha1_hmac"], hmac):
        return error("Invalid hmac", error_codename="invalid_hmac")

    voter = voters.first()
    data['voter'] = voter
    return RET_PIPE_CONTINUE

def mark_voted_in_minshu(data, **kwargs):
    '''
    Registers the ID in the minshu census
    '''
    import requests
    from crypto import hash_str

    hashed_dni = data["voter"].dni
    url = "%(base_url)s/api/v1/voter" % dict(
        base_url= kwargs["base_url"]
    )
    data = dict(
        value=hashed_dni,
        extra=""
    )
    headers = {}

    # TODO: use authentication
    r = requests.post(url, data=data, headers=headers)
    if r.status_code == 200:
        return RET_PIPE_CONTINUE
    else:
        return error("Error registering the id", error_codename="unknown_error")

def mark_id_authenticated(data):
    from app import db
    from models import Voter

    voter = data['voter']

    voter.status = Voter.STATUS_VOTED
    voter.modified = datetime.utcnow()
    db.session.add(voter)
    db.session.commit()

    return make_response("", 200)

def execute_pipeline(data, pipeline = None):
    '''
    Executes a pipeline of functions.

    If pipeline is empty, it  uses the config parameter SMS_CHECKS_PIPELINE by
    default. The pipeline must be a list of pairs. Each pair contains
    (checker_path, params), where checker is the path to the module and
    function name of the checker, and params is either None or a dictionary
    with extra parameters accepted by the checker.

    Checkers must accept always at least one parameter, data, that is an object
    that is passed from pipe to pipe.

    Checkers are allowed to modify the "data" object to use it as a way to
    communicate with the following checkers in the pipeline, and also to
    communicate or store any information for the caller.

    Checkers return either:
    * RET_PIPE_CONTINUE in which case next checker in the pipeline is called.
    * RET_PIPE_SUCCESS in which case pipeline stops directly without an error.
      Useful for whitelisting, for example.
    * anything else, in which case we assume it's an error, so the pipeline
      stops and returns that value.
    '''
    if pipeline is None:
        pipeline = current_app.config.get('SMS_CHECKS_PIPELINE', [])

    for checker_path, kwargs in pipeline:
        # get access to the function
        func_name = checker_path.split(".")[-1]
        module = __import__(
            ".".join(checker_path.split(".")[:-1]), globals(), locals(),
            [func_name], 0)
        fargs = dict(data=data)
        if kwargs is not None:
            fargs.update(kwargs)
        ret = getattr(module, func_name)(**fargs)
        if ret == RET_PIPE_CONTINUE:
            continue
        elif ret == RET_PIPE_SUCCESS:
            return True
        else:
            return ret

    return True
