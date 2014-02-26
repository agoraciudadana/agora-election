#!/usr/bin/env python3
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

import os
import logging
import argparse

from prettytable import PrettyTable
from celery import Celery

from flask import Flask
from flask.ext.sqlalchemy import SQLAlchemy
from flask.ext.babel import Babel

# bootstrap our app
app_flask = Flask(__name__)
babel = Babel(app_flask)
db = SQLAlchemy(app_flask)
app = Celery("app")

from tasks import *
from views import api
from models import ColorList, Message, Voter
app_flask.register_blueprint(api, url_prefix='/api/v1')

def config():
    logging.basicConfig(level=logging.DEBUG)
    app_flask.config.from_object("settings")
    app.config_from_object("settings")

    settings_file = os.environ.get('AGORA_ELECTION_SETTINGS', None)
    if settings_file is not None:
        if not os.path.isabs(settings_file):
            os.environ['AGORA_ELECTION_SETTINGS'] = os.path.abspath(settings_file)
        logging.debug("AGORA_ELECTION_SETTINGS = %s" % os.environ['AGORA_ELECTION_SETTINGS'])
        app_flask.config.from_envvar('AGORA_ELECTION_SETTINGS', silent=False)

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("-d", "--createdb", help="create the database",
                        action="store_true")
    parser.add_argument("-c", "--console", help="agora-election command line",
                        action="store_true")
    parser.add_argument("-s", "--send", help="send sms action",
                        action="store_true")
    parser.add_argument("-w", "--whitelist", help="whitelist an item",
                        action="store_true")
    parser.add_argument("-b", "--blacklist", help="blacklist an item",
                        action="store_true")
    parser.add_argument("-m", "--message", help="message to be sent")
    parser.add_argument("-i", "--ip", help="ip address")
    parser.add_argument("-l", "--list-show", help="show list", action="store_true")
    parser.add_argument("-r", "--remove", help="remove item from black or white list", action="store_true")
    parser.add_argument("-t", "--tlf", help="telephone number")
    pargs = parser.parse_args()

    if pargs.createdb:
        logging.info("creating the database: %s" % app_flask.config.get('SQLALCHEMY_DATABASE_URI', ''))
        db.create_all()
        return
    elif pargs.console:
        import ipdb; ipdb.set_trace()
        return
    elif pargs.send:
        if pargs.tlf.startswith("+34"):
            tlf = pargs.tlf
        else:
            tlf = "+34" + pargs.tlf
        kwargs = dict(
            receiver = tlf,
            content = pargs.message
        )
        from views import token_generator
        msg = Message(
            tlf=tlf,
            lang_code=current_app.config.get("BABEL_DEFAULT_LOCALE", "en"),
            token=pargs.message
        )
        db.session.add(msg)
        db.session.commit()
        send_sms.apply_async(kwargs=dict(msg_id=msg.id),
            expires=app_flask.config.get('SMS_EXPIRE_SECS', 120))
        return
    elif pargs.list_show:
        key = None
        if pargs.ip:
            key = ColorList.KEY_IP
            value = pargs.ip
        elif pargs.tlf:
            key = ColorList.KEY_TLF
            value = pargs.tlf

        action = None
        if pargs.whitelist:
            action = ColorList.ACTION_WHITELIST
        elif pargs.blacklist:
            action = ColorList.ACTION_BLACKLIST

        if action is None and key is None:
            items = db.session.query(ColorList)
        if action is None:
            items  = db.session.query(ColorList)\
                .filter(ColorList.key == key, ColorList.value == value)
        elif key is None:
            items = db.session.query(ColorList)\
                .filter(ColorList.action == action)
        else:
            items = db.session.query(ColorList)\
                .filter(ColorList.key == key,
                        ColorList.action == action,
                        ColorList.value == value)

        def str_action(task):
            if task.action == ColorList.ACTION_WHITELIST:
                return "whitelist"
            elif task.action == ColorList.ACTION_BLACKLIST:
                return "blacklist"

        def str_key(task):
            if task.key == ColorList.KEY_IP:
                return "ip"
            elif task.key == ColorList.KEY_TLF:
                return "tlf"

        table = PrettyTable(['id', 'action', 'key', 'value', 'created'])

        print("%d rows:" % items.count())
        for task in items:
            table.add_row([str(task.id), str_action(task), str_key(task),
                           task.value, task.created])
        print(table)
        return

    elif pargs.whitelist or pargs.blacklist:
        action = ColorList.ACTION_WHITELIST if pargs.whitelist else ColorList.ACTION_BLACKLIST
        if pargs.ip:
            key = ColorList.KEY_IP
            value = pargs.ip
        else:
            key = ColorList.KEY_TLF
            value = pargs.tlf

        item = db.session.query(ColorList)\
            .filter(ColorList.key == key,
                    ColorList.action == action,
                    ColorList.value == value).first()
        if item is not None:
            logging.warn("It's listed already that way, nothing to do!")
            return

        cl = ColorList(key=key, action=action, value=value)
        db.session.add(cl)
        db.session.commit()
        return

    logging.info("using provider = %s" % app_flask.config.get('SMS_PROVIDER', None))
    port = app_flask.config.get('SERVER_PORT', None)
    app_flask.run(threaded=True, use_reloader=False, port=port)

# needs to be called in celery too
config()

if __name__ == "__main__":
    main()
