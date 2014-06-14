# -*- coding: utf-8 -*-
#
# This file is part of agora-election.
# Copyright (C) 2013, 2014 Eduardo Robles Elvira <edulix AT agoravoting DOT com>

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
from sqlalchemy.exc import InvalidRequestError, DBAPIError

from sqlalchemy.orm import exc as sa_exc

from checks import *
from app import db, app_mail
from crypto import constant_time_compare, salted_hmac, get_random_string, hash_token

def get_ip(request):
    getter = current_app.config.get('REAL_IP_GETTER', 'remote_addr')
    if getter == 'remote_addr':
        return request.remote_addr
    else:
        return request.headers[getter]

def token_generator():
    '''
    Generate an user token string. 8 alfanumeric characters. We do not allow
    confusing characters: 0,O,I,1
    '''
    return get_random_string(8, 'ABCDEFGHJKLMNPQRSTUVWXYZ23456789')

def set_serializable():
    # if using postgres, then we check concurrency
    if "postgres" in current_app.config.get("SQLALCHEMY_DATABASE_URI", ""):
        import psycopg2
        # commit to separate everything in a new transaction
        db.session.commit()
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

def serializable_retry(func, max_num_retries=None):
    '''
    This decorator calls another function whose next commit will be serialized.
    This might triggers a rollback. In that case, we will retry with some
    increasing (5^n * random, where random goes from 0.5 to 1.5 and n starts
    with 1) timing between retries, and fail after a max number of retries.
    '''
    def wrap(max_num_retries, *args, **kwargs):
        if max_num_retries is None:
            max_num_retries = current_app.config.get(
                'MAX_NUM_SERIALIZED_RETRIES', 5)

        retries = 1
        initial_sleep_time = 5 # miliseconds

        set_serializable()
        while True:
            try:
                ret = func(*args, **kwargs)
                break
            except (InvalidRequestError, DBAPIError) as e:
                db.session.rollback()
                if retries > max_num_retries:
                    unset_serializable()
                    db.session.commit()
                    raise e

                retries += 1
                sleep_time = (initial_sleep_time**retries) * (random.random() + 0.5)
                time.sleep(sleep_time * 0.001) # specified in seconds
            except Exception as e:
                raise e

        unset_serializable()
        db.session.commit()
        return ret

    return partial(wrap, max_num_retries)