import datetime
import json

from oauth2client.client import OAuth2Credentials
from sqlalchemy import UniqueConstraint

from app import db
from .constants import Platform


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
    platform = db.Column(db.Enum(Platform))
    platform_id = db.Column(db.String(100))
    # relations
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    user = db.relationship('User', backref=db.backref('playlists', lazy='dynamic'))

    __table_args__ = (UniqueConstraint('platform', 'platform_id', name='_platform_platformid_constraint'),)

    def __init__(self, name, channel_id, platform, platform_id, user_id):
        self.name = name
        self.channel_id = channel_id
        self.platform = platform
        self.platform_id = platform_id
        self.user_id = user_id


class User(db.Model, BaseModelMixin):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100))
    slack_id = db.Column(db.String(100), index=True, unique=True)
    last_posted_auth_error = db.Column(db.DateTime, default=now)
    credentials = db.relationship('Credential', backref='user', lazy='dynamic')
    is_service_user = db.Column(db.Boolean, default=False)

    def __init__(self, name, slack_id):
        self.name = name
        self.slack_id = slack_id

    def credentials_for_platform(self, platform):
        platform_creds = [c for c in self.credentials if c.platform is platform]
        if not platform_creds:
            return None
        if len(platform_creds) > 1:
            # TODO: what do here?
            pass
        return platform_creds[0].to_oauth2_creds()


class Credential(db.Model, BaseModelMixin):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), index=True)
    platform = db.Column(db.Enum(Platform))
    credentials = db.Column(db.String(5000))

    __table_args__ = (UniqueConstraint('user_id', 'platform', name='_user_platform_constraint'),)

    def __init__(self, user_id, platform, credentials):
        self.user_id = user_id
        self.platform = platform
        self.credentials = credentials

    def to_oauth2_creds(self):
        if self.platform is Platform.YOUTUBE:
            return OAuth2Credentials.from_json(self.credentials)
        elif self.platform is Platform.SPOTIFY:
            return json.loads(self.credentials)

