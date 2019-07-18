import json
import time

from spotipy import oauth2

from .constants import Platform
from .models import User

from settings import SPOTIFY_CLIENT_ID, SPOTIFY_CLIENT_SECRET, SPOTIFY_REDIRECT_URI


class SpotipyClientCredentialsManager(object):
    def __init__(self, credentials):
        self.credentials = credentials

    # shamelessly copy/pasted from spotipy.oauth2.SpotifyClientCredentials
    def _is_token_expired(self, token_info):
        now = int(time.time())
        return token_info['expires_at'] - now < 60

    def get_access_token(self):
        if self._is_token_expired(self.credentials):
            spotify_oauth = SpotipyDBWrapper(
                client_id=SPOTIFY_CLIENT_ID,
                client_secret=SPOTIFY_CLIENT_SECRET,
                redirect_uri=SPOTIFY_REDIRECT_URI
            )
            refresh_credentials = spotify_oauth.refresh_access_token(self.credentials['refresh_token'])
            slack_id, slack_user_name = self.credentials['userdata'].split(':')
            user = User.query.filter_by(slack_id=slack_id).first()
            creds = [creds for creds in user.credentials if creds.service is Platform.SPOTIFY][0]
            old_creds = creds.to_oauth2_creds()
            old_creds.update(refresh_credentials)
            creds.credentials = json.dumps(old_creds)
            creds.save()
            self.credentials = old_creds

        return self.credentials['access_token']


class SpotipyDBWrapper(oauth2.SpotifyOAuth):
    def __init__(self, *args, **kwargs):
        super(SpotipyDBWrapper, self).__init__(*args, **kwargs)
        self.creds = None

    def _save_token_info(self, token_info):
        if self.creds:
            self.creds.credentials = json.dumps(token_info)

    def _add_custom_values_to_token_info(self, token_info):
        token_info = super(SpotipyDBWrapper, self)._add_custom_values_to_token_info(token_info=token_info)

        if self.state:
            token_info['userdata'] = self.state

        return token_info