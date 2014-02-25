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

import sys
import os
import logging
import argparse
from flask import Flask
from celery import Celery
from flask.ext.sqlalchemy import SQLAlchemy
from flask.wrappers import Request, _missing, _get_data

app_flask = Flask(__name__)

@app_flask.route("/")
def hello():
    return "Hello World!"

# boostrap our little application
db = SQLAlchemy(app_flask)

app = Celery("app")

from tasks import *

def main():
    logging.basicConfig(level=logging.DEBUG)
    app_flask.config.from_object("settings")

    settings_file = os.environ.get('AGORA_ELECTION_SETTINGS', None)
    if settings_file is not None:
        if not os.path.isabs(settings_file):
            os.environ['AGORA_ELECTION_SETTINGS'] = os.path.abspath(settings_file)
        logging.debug("AGORA_ELECTION_SETTINGS = %s" % os.environ['AGORA_ELECTION_SETTINGS'])
        app_flask.config.from_envvar('AGORA_ELECTION_SETTINGS', silent=False)
    else:
        logging.warning("AGORA_ELECTION_SETTINGS not set")

    parser = argparse.ArgumentParser()
    parser.add_argument("--createdb", help="create the database",
                        action="store_true")
    parser.add_argument("--console", help="frestq command line",
                        action="store_true")
    pargs = parser.parse_args()

    if pargs.createdb:
        logging.info("creating the database: %s" % self.config.get('SQLALCHEMY_DATABASE_URI', ''))
        db.create_all()
        return
    elif pargs.console:
        import ipdb; ipdb.set_trace()
        return

    port = app_flask.config.get('SERVER_PORT', None)
    app_flask.run(threaded=True, use_reloader=False, port=port)

if __name__ == "__main__":
    main()
