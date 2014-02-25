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
from flask import Flask
from celery import Celery
from flask.ext.sqlalchemy import SQLAlchemy

app_flask = Flask(__name__)


# boostrap our little application
db = SQLAlchemy(app_flask)

app = Celery("app")

from tasks import *
from views import api
app_flask.register_blueprint(api, url_prefix='/')

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
    parser.add_argument("-b", "--createdb", help="create the database",
                        action="store_true")
    parser.add_argument("-c", "--console", help="agora-election command line",
                        action="store_true")
    parser.add_argument("-s", "--send", help="send sms action",
                        action="store_true")
    parser.add_argument("-r", "--receiver", help="SMS receiver telephone number")
    parser.add_argument("-m", "--message", help="message to be sent")
    pargs = parser.parse_args()

    if pargs.createdb:
        logging.info("creating the database: %s" % app_flask.config.get('SQLALCHEMY_DATABASE_URI', ''))
        db.create_all()
        return
    elif pargs.console:
        import ipdb; ipdb.set_trace()
        return
    elif pargs.send:
        kwargs = dict(
            receiver = "+34" + pargs.receiver,
            content = pargs.message
        )
        send_sms.apply_async(kwargs=kwargs, expires=120)
        return

    port = app_flask.config.get('SERVER_PORT', None)
    app_flask.run(threaded=True, use_reloader=False, port=port)

# needs to be called in celery too
config()

if __name__ == "__main__":
    main()
