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
import re
import random
import time
import codecs
from functools import partial

from flask import Blueprint, request, make_response, render_template, url_for
from flask.ext.mail import Message as MailMessage
from flask.ext.babel import gettext, ngettext
from flask.ext.captcha.models import CaptchaStore
from flask import current_app
from jinja2 import Markup
from sqlalchemy.exc import InvalidRequestError, DBAPIError
from sqlalchemy.orm import exc as sa_exc

from prettytable import PrettyTable

from checks import *
from app import db, app_mail
from crypto import constant_time_compare, salted_hmac, get_random_string, hash_token

def get_ip(request):
    getter = current_app.config.get('REAL_IP_GETTER', 'remote_addr')
    if getter == 'remote_addr':
        return request.remote_addr
    else:
        return request.headers[getter]

def token_generator(is_audio_token=False):
    '''
    Generate an user token string.

    If is_audio_token is False, it a string of 8 alfanumeric characters. We do
    not allow confusing characters: 0,O,I,1.

    If is_audio_token is True, the it generates string of 8 numeric characters.
    The string always starts with a non-zero number, so it's guaranteed to be
    8 characters long (and thus there are 90 million possibilities)
    '''
    if not is_audio_token:
        return get_random_string(8, 'ABCDEFGHJKLMNPQRSTUVWXYZ23456789')
    else: #use only numbers: large numbers (8 chars always)
        return get_random_string(1, '123456789') + get_random_string(7, '0123456789')

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

def read_csv_to_dicts(path, sep=";", key_column=0):
    '''
    Given a file in CSV format, convert it to a dictionary.
    Example file (example.csv):

    ID,Name,Comment
    1,Fulanito de tal,Nothing of interest
    2,John Doe,

    This file would be converted into the following if you call to
    read_csv_to_dicts("example.csv", sep=","):
    {
        "1": {
            "ID": "1",
            "Name": "Fulanito de tal",
            "Comment": "Nothing of interest"
        },
        "2": {
            "ID": "1",
            "Name": "Fulanito de tal",
            "Comment": ""
        }
    }
    '''
    ret = dict()
    n = 0
    with codecs.open(path, mode='r', encoding="utf-8", errors='strict') as f:
        headers = f.readline().split(sep)
        n += 1
        for line in f:
            line = line.rstrip()
            n += 1
            item = dict()
            values = line.split(sep)
            for key, value in zip(headers, values):
                item[key] = value

            # parse id num..
            id_num = values[key_column].upper().strip()
            id_num = re.sub("[^0-9A-Z]", '', id_num)

            if id_num[0] not in 'XYZ':
                id_num = re.sub("[^0-9]", '', id_num)
                # recalc letter just in case..
                mod_letters = 'TRWAGMYFPDXBNJZSQVHLCKE'
                id_num = id_num + mod_letters[int(id_num) % 23]
                if len(id_num) < 9:
                    id_num = "0"*(9-len(id_num)) + id_num

            ret[id_num] = item
    return ret

def format_print_table_output(output_format, table_header, items, row_getter,
                              **kwargs):
    '''
    Use this to format the output of a table.

    Options:
    * output_format (str): Values allowed: 'table', 'csv', 'json'
    * table_header (list): list of strings for the table header
    * items: iterable list of items to be shown
    * row_getter (func): function that receives an item from 'items' and returns
      a list of strings to be shown as a row
    * kwargs: more options. you can specify the "separator" character for csv
      format, for example (comma by default)
    '''
    if output_format == "table":
        table = PrettyTable(table_header)
        print("%d rows:" % items.count())
        for item in items:
            table.add_row(row_getter(item))
        print(table)
    elif output_format == 'csv':
        def l_str_join(sep, l):
            return sep.join([str(i) for i in l])

        sep = kwargs.get('separator', ',')
        print(l_str_join(sep, table_header))
        for item in items:
            print(l_str_join(sep, row_getter(item)))
    else: # json
        l = []
        for item in items:
            row = row_getter(item)
            l.append(dict([(key, str(val))
                           for key, val in zip(table_header, row)]))

        print(json.dumps(l, indent=4))
