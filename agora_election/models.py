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

from app import db
from datetime import datetime

class Voter(db.Model):
    '''
    Represents a voter for an election
    '''
    __tablename__ = 'voter'

    # Everytime an user request to identify, we register it in the database with
    # this status, even if it fails for whatever reason (for example if it's
    # in the blacklist)
    STATUS_REQUESTED = -1

    # This is the status set to a voter when he is elegible to be sent an SMS
    # and we have sent the send-sms task to celery, but celery has not processed
    # it yet
    STATUS_CREATED = 0

    # This is the status set when celery has already sent to the SMS provider
    # the task of sending an SMS to a voter. Note that currently we don't check
    # in background if the SMS provider really sends the SMS.
    STATUS_SENT = 1

    # Status set when the user has correctly authenticated using the one time
    # password sent via SMS
    STATUS_AUTHENTICATED = 2

    # Status set when agora-ciudadana has notified us to mark the voter as voted
    # This happens when the user has already entered the voting booth and sent
    # the vote.
    # IMPORTANT: Any successful vote will necessarily have this status.
    STATUS_VOTED = 3

    # Status set to a Voter that was previously in status "requested" when we
    # remove an ip from the blacklist
    STATUS_REQUESTED_IGNORE = -2

    id = db.Column(db.Integer, db.Sequence('voter_id_seq'), primary_key=True)

    election_id = db.Column(db.Integer, index=True)

    created = db.Column(db.DateTime, default=datetime.utcnow, index=True)

    modified = db.Column(db.DateTime, default=datetime.utcnow)

    ip = db.Column(db.String(45), index=True)

    tlf = db.Column(db.String(20), index=True)

    first_name = db.Column(db.String(60))

    last_name = db.Column(db.String(100))

    email = db.Column(db.String(140))

    dni = db.Column(db.String(512))

    postal_code = db.Column(db.String(140))

    lang_code = db.Column(db.String(6))

    receive_mail_updates = db.Column(db.Boolean)

    token_guesses = db.Column(db.Integer, default=0)

    message_id = db.Column(db.Integer, db.ForeignKey('message.id'))

    message = db.relationship('Message',
        backref=db.backref('voters', lazy='dynamic'))

    is_active = db.Column(db.Boolean)

    # created|sms-sent|authenticated|voted
    status = db.Column(db.Integer, index=True)

    def __init__(self, **kwargs):
        for key, value in kwargs.items():
            setattr(self, key, value)

    def __repr__(self):
        return '<Voter %r>' % self.id


class ColorList(db.Model):
    '''
    Represents a white/black list
    '''
    __tablename__ = 'colorlist'

    ACTION_WHITELIST = 0
    ACTION_BLACKLIST = 1
    KEY_IP = 0
    KEY_TLF = 1

    id = db.Column(db.Integer, db.Sequence('user_id_seq'), primary_key=True)

    # white, black
    action = db.Column(db.Integer, index=True)

    # ip, tlf
    key = db.Column(db.Integer, index=True)

    value = db.Column(db.String(45), index=True)

    created = db.Column(db.DateTime, default=datetime.utcnow)

    modified = db.Column(db.DateTime, default=datetime.utcnow)

    def __init__(self, **kwargs):
        for key, value in kwargs.items():
            setattr(self, key, value)

    def __repr__(self):
        return '<ColorList %r>' % self.id


class Message(db.Model):
    '''
    Represents message list
    '''
    __tablename__ = 'message'

    STATUS_QUEUED = 0
    STATUS_SENT = 1
    STATUS_IGNORE =  2

    id = db.Column(db.Integer, db.Sequence('message_id_seq'), primary_key=True)

    created = db.Column(db.DateTime, default=datetime.utcnow)

    modified = db.Column(db.DateTime, default=datetime.utcnow)

    tlf = db.Column(db.String(20), index=True)

    ip = db.Column(db.String(45), index=True)

    content = db.Column(db.String(160))

    token = db.Column(db.String(256))

    authenticated = db.Column(db.Boolean, default=False)

    lang_code = db.Column(db.String(6))

    # queued, sent
    status = db.Column(db.Integer, index=True)

    sms_status = db.Column(db.String(20), default="")

    sms_response = db.Column(db.String(400), default="")

    def __init__(self, **kwargs):
        for key, value in kwargs.items():
            setattr(self, key, value)

    def __repr__(self):
        return '<Message %r>' % self.id
