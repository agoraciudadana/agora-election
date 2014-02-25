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

class Message(db.Model):
    '''
    Represents an message
    '''
    __tablename__ = 'message'

    id = db.Column(db.Integer, db.Sequence('user_id_seq'), primary_key=True)

    created = db.Column(db.DateTime())

    modified = db.Column(db.DateTime())

    ip = db.Column(db.String(20))

    dest = db.Column(db.String(16))

    msg = db.Column(db.String(160))

    status = db.Column(db.Integer, index=True)

    sms_status = db.Column(db.String(20))

    sms_response = db.Column(db.String(400))

    def __init__(self, **kwargs):
        for key, value in kwargs.iteritems():
            setattr(self, key, value)

    def __repr__(self):
        return '<Message %r>' % self.id
