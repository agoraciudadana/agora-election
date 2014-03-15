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

import logging
from datetime import datetime
from flask.ext.babel import gettext, ngettext

from app import app, app_flask
from sms import SMSProvider

@app.task
def send_sms(msg_id, token):
    '''
    Sends an sms with a given content to the receiver
    '''
    from app import db
    from models import Message, Voter

    # get the msg
    msg = db.session.query(Message)\
        .filter(Message.id == msg_id).first()
    if msg is None:
        raise Exception("Message with id = %d not found" % msg_id)
    if msg.status != Message.STATUS_QUEUED:
        raise Exception("Message msg id = %d is not in "
            "queued status (0), but '%d'" % (msg_id, msg.status))

    voter = msg.voters.first()
    if not voter.is_active:
        logging.warn("not sending msg with id = %d because voter is not "
                     "active anymore" % msg_id)
        return

    # forge the message using the token
    site_name = app_flask.config.get("SITE_NAME", "")
    content = gettext(
        app_flask.config.get("SMS_MESSAGE", ""),
        token=token, server_name=site_name)

    # update status
    msg.status = Message.STATUS_SENT
    msg.content = content
    msg.modified = datetime.utcnow()
    voter = msg.voters.first()
    voter.status = Voter.STATUS_SENT
    voter.modified = datetime.utcnow()
    db.session.add(msg)
    db.session.add(voter)
    db.session.commit()

    # actually send the sms
    provider = SMSProvider.get_instance()
    provider.send_sms(msg.tlf, content)
