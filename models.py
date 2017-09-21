import datetime
import json
from oauth2client.client import OAuth2Credentials

from sqlalchemy import UniqueConstraint

from application import db
from constants import MusicService


def now():
    datetime.datetime.now()


class BaseModelMixin(object):
    def __rep__(self):
        return "<%s  %s>" % (self.__class__.__name__, self.id)

    def save(self):
        db.session.add(self)
        db.session.commit()

    def delete(self):
        db.session.delete(self)
        db.session.commit()


class Playlist(db.Model, BaseModelMixin):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100))
    channel_id = db.Column(db.String(100))
    service = db.Column(db.Enum(MusicService))
    service_id = db.Column(db.String(100))
    # relations
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    user = db.relationship('User', backref=db.backref('playlists', lazy='dynamic'))

    __table_args__ = (UniqueConstraint('service', 'service_id', name='_service_serviceid_constraint'),)

    def __init__(self, name, channel_id, service, service_id, user_id):
        self.name = name
        self.channel_id = channel_id
        self.service = service
        self.service_id = service_id
        self.user_id = user_id


class User(db.Model, BaseModelMixin):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100))
    slack_id = db.Column(db.String(100), index=True, unique=True)
    last_posted_auth_error = db.Column(db.DateTime, default=now)
    credentials = db.relationship('Credential', backref='user', lazy='dynamic')

    def __init__(self, name, slack_id):
        self.name = name
        self.slack_id = slack_id

    def credentials_for_service(self, service):
        service_creds = [c for c in self.credentials if c.service is service]
        if not service_creds:
            return None
        if len(service_creds) > 1:
            # TODO: what do here?
            pass
        return service_creds[0].to_oauth2_creds()


class Credential(db.Model, BaseModelMixin):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), index=True)
    service = db.Column(db.Enum(MusicService))
    credentials = db.Column(db.String(5000))

    __table_args__ = (UniqueConstraint('user_id', 'service', name='_user_service_constraint'),)

    def __init__(self, user_id, service, credentials):
        self.user_id = user_id
        self.service = service
        self.credentials = credentials

    def to_oauth2_creds(self):
        if self.service is MusicService.YOUTUBE:
            return OAuth2Credentials.from_json(self.credentials)
        elif self.service is MusicService.SPOTIFY:
            return json.loads(self.credentials)

