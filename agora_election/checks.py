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
from datetime import datetime

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

def check_has_not_voted(ip_addr, data):
    '''
    check that tlf should have not voted
    '''
    from app import db
    from models import Voter

    curr_eid = current_app.config.get("CURRENT_ELECTION_ID", 0)

    voter = db.session.query(Voter)\
        .filter(Voter.election_id == curr_eid,
                Voter.tlf == data["tlf"],
                Voter.status == 'voted',
                Voter.is_active == True).first()
    if voter is not None:
        return error("Voter already voted", field="tlf",
                     error_codename="already_voted")
    return RET_PIPE_CONTINUE

def check_tlf_whitelisted(ip_addr, data):
    '''
    If tlf is whitelisted, accept
    '''
    from app import db
    from models import ColorList

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

def check_ip_whitelisted(ip_addr, data):
    '''
    If ip is whitelisted, then do not blacklist by ip in the following checkers
    '''
    from app import db
    from models import ColorList

    item = db.session.query(ColorList)\
        .filter(ColorList.key == ColorList.KEY_IP,
                ColorList.value == ip_addr).first()
    if item is not None:
        if item.action == ColorList.ACTION_WHITELIST:
            data["ip_whitelisted"] = True
            data["ip_blacklisted"] = False
        else:
            data["ip_blacklisted"] = True
    else:
        data["ip_blacklisted"] = False
    return RET_PIPE_CONTINUE

def check_blacklisted(ip_addr, data):
    '''
    check if tlf or ip are blacklisted
    '''
    from app import db
    from models import ColorList

    # optimization: if we have already gone through the whitelisting checking
    # we don't have do new queries
    if 'ip_blacklisted' in data and 'tlf_blacklisted' in data:
        if data['ip_blacklisted'] or data['tlf_blacklisted']:
            return error("Blacklisted", error_codename="blacklisted")

        return RET_PIPE_CONTINUE

    item = db.session.query(ColorList)\
        .filter(ColorList.key == ColorList.KEY_TLF,
                ColorList.action == ColorList.ACTION_BLACKLIST,
                ColorList.value == data["tlf"]).first()
    if item is not None:
        return error("Blacklisted", error_codename="blacklisted")

    item = db.session.query(ColorList)\
        .filter(ColorList.key == ColorList.KEY_IP,
                ColorList.action == ColorList.ACTION_BLACKLIST,
                ColorList.value == ip_addr).first()
    if item is not None:
        return error("Blacklisted", error_codename="blacklisted")

    return RET_PIPE_CONTINUE

def check_ip_blacklisted(ip_addr, data):
    '''
    If ip is whitelisted, then do not blacklist by ip in the following checkers
    '''
    from app import db
    from models import ColorList

    item = db.session.query(ColorList)\
        .filter(ColorList.key == ColorList.KEY_IP,
                ColorList.action == ColorList.ACTION_WHITELIST,
                ColorList.value == ip_addr).first()
    if item is not None:
        data["ip_whitelisted"] = True
    return RET_PIPE_CONTINUE

def check_registration_pipeline(ip_addr, data):
    '''
    Does a deeper check on the input data when creating an election. These are
    the default constraints in order:
    1. tlf should have not voted in this election
    2. if tlf is whitelisted, then accept. Else, continue checking:
    3. if ip is whitelisted, then do not blacklist by ip in the following
       checkers
    4. tlf, ip should not be blacklisted

    TODO:
    5. if tlf has been sent >=7 failed-sms in total, error, blacklist
    6. if tlf has been sent more than >=3 failed-sms last hour, error, wait
    7. if tlf has been sent 1 failed-sms last 3 minutes, error, wait
    8  if ip has been sent >= 7 failed-sms last day, error, blacklist
    9. success!

    This uses the config parameter CHECKS_PIPELINE, that must be a list of
    pairs. Each pair contains (checker_path, params), where checker is the
    path to the module and function name of the checker, and params is either
    None or a dictionary with extra parameters accepted by the checker.

    Checkers must accept always at least two parameters:
    * ip_addr: string containing the ip address of the form sender.
    * data: will be the dict data that comes from the resgistration form (see
    details in agora.election.views.post_register). It's been already minimally
    sanitized.

    Checkers are allowed to modify data dict to use it as a way to communicate
    with the following checkers in the pipeline.

    Checkers return either:
    * RET_PIPE_CONTINUE in which case next checker in the pipeline is called
    * RET_PIPE_SUCCESS in which case pipeline stops directly without an error.
      Useful for whitelisting, for example.
    * an instance of flask.Response, in which case we assume it's an error we
      have to show.
    '''
    pipeline = current_app.config.get('CHECKS_PIPELINE', [])

    for checker_path, kwargs in pipeline:
        # get access to the function
        func_name = checker_path.split(".")[-1]
        module = __import__(
            ".".join(checker_path.split(".")[:-1]), globals(), locals(),
            [func_name], 0)
        fargs = dict(ip_addr=ip_addr, data=data)
        if kwargs is not None:
            fargs.update(fargs)
        ret = getattr(module, func_name)(**fargs)
        if ret == RET_PIPE_CONTINUE:
            continue
        elif ret == RET_PIPE_SUCCESS:
            return True
        else:
            return ret

    return True
