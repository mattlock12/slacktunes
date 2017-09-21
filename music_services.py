import json
import httplib2
from functools import wraps

from apiclient.discovery import build
from oauth2client.client import OAuth2WebServerFlow
from spotipy import Spotify as Spotipy
from spotipy.client import SpotifyException

from constants import InvalidEnumException, MusicService
from oauth_wrappers import SpotipyClientCredentialsManager, SpotipyDBWrapper
from settings import YOUTUBE_CLIENT_ID, YOUTUBE_CLIENT_SECRET, YOUTUBE_REDIRECT_URI, SPOTIFY_CLIENT_ID, SPOTIFY_CLIENT_SECRET, SPOTIFY_REDIRECT_URI
from utils import strip_spotify_track_id, strip_youtube_video_id


class NoCredentialsError(Exception):
    pass


class SimpleJSONWrapper(object):
    def __init__(self, data_dict):
        self.data_dict = data_dict

    def to_json(self):
        return json.dumps(self.data_dict)


def credentials_required(f):
    @wraps(f)
    def decorated_function(cls_or_self, *args, **kwargs):
        if not cls_or_self.credentials:
            raise NoCredentialsError
        return f(cls_or_self, *args, **kwargs)
    return decorated_function



class ServiceBase(object):
    def __init__(self, credentials):
        self.credentials = credentials
        self.service = None
        self.tracks_in_playlist = {}

    @classmethod
    def from_string(cls, string):
        if string.lower()[0] == 'y':
            return Youtube
        elif string.lower()[0] == 's':
            return Spotify
        elif string.lower()[0] == 'g':
            return GMusic
        else:
            raise Exception("Invalid service")

    @classmethod
    def from_link(self, link):
        if 'yout' in link:
            return Youtube
        elif 'spotify' in link:
            return Spotify
        elif 'play.google.com/music' in link:
            return GMusic
        else:
            return None

    @classmethod
    def from_enum(cls, enum):
        if enum is MusicService.YOUTUBE:
            return Youtube
        elif enum is MusicService.SPOTIFY:
            return Spotify
        elif enum is MusicService.GMUSIC:
            return GMusic
        else:
            raise InvalidEnumException


    @classmethod
    def get_flow(cls):
        raise NotImplementedError

    @classmethod
    def get_auth_uri(cls, state=None):
        raise NotImplementedError

    @classmethod
    def exchange(cls, code, state):
        raise NotImplementedError

    @credentials_required
    def add_link_to_playlist(self, playlist, link):
        if not self.is_same_service_link(link):
            return False, "Cross service links not currently supported"

        existing_track_ids = self.tracks_in_playlist.get(playlist.service_id, set())
        if not existing_track_ids:
            existing_track_ids = self.tracks_in_playlist[playlist.service_id] = self.list_tracks_in_playlist(playlist)

        track_id = self.get_track_id(link)
        if not track_id:
            return False, "Could not parse video id"

        if track_id in existing_track_ids:
            return False, "Already in playlist"

        return self.add_track_to_playlist_by_track_id(playlist=playlist, track_id=track_id)


class Youtube(ServiceBase):
    SCOPE = 'https://www.googleapis.com/auth/youtube'
    API_SERVICE_NAME = "youtube"
    API_VERSION = "v3"
    NAME = 'Youtube'

    @classmethod
    def get_flow(cls):
        return OAuth2WebServerFlow(client_id=YOUTUBE_CLIENT_ID,
                                   client_secret=YOUTUBE_CLIENT_SECRET,
                                   scope=cls.SCOPE,
                                   redirect_uri=YOUTUBE_REDIRECT_URI
                                   )

    @classmethod
    def get_auth_uri(cls, state=None):
        flow = cls.get_flow()
        flow.params['access_type'] = 'offline'
        if state:
            flow.params['state'] = state
        return flow.step1_get_authorize_url()

    @classmethod
    def exchange(cls, code, state):
        flow = cls.get_flow()
        return flow.step2_exchange(code)

    def _get_playlist_create_body(self, playlist_name, channel_id):
        return {
        "status": {
            "privacyStatus": "Public",
        },
        "kind": "youtube#playlist",
        "snippet": {
            "description": "slacktunes created playlist! Check out https://slacktunes.me", # The playlist's description.
            "tags": [ "slacktunes",],
            "channelId": channel_id,
            "title": playlist_name,
            },
        }

    def is_same_service_link(self, link):
        return 'yout' in link

    def get_track_id(self, link):
        return strip_youtube_video_id(link)

    @credentials_required
    def get_wrapped_service(self):
        if self.service:
            return self.service

        http_auth = self.credentials.authorize(httplib2.Http())
        return build(self.API_SERVICE_NAME, self.API_VERSION, http=http_auth)

    @credentials_required
    def list_playlists(self):
        service = self.get_wrapped_service()

        playlists = []
        playlists_request = service.playlists().list(part='snippet', mine=True, maxResults=50)
        while playlists_request:
            playlists_response = playlists_request.execute()
            for pl in playlists_response['items']:
                playlists.append(pl)
            playlists_request = service.playlists().list_next(playlists_request, playlists_response)

        return playlists

    @credentials_required
    def create_playlist(self, playlist_name, user_id):
        service = self.get_wrapped_service()

        channels_response = service.channels().list(part='id', mine=True).execute()
        if not channels_response or not channels_response['items']:
            # TODO: figure out error handling
            return False, "No channels"

        channel_id = channels_response['items'][0]['id']

        for pl in self.list_playlists():
            if pl['snippet']['title'] == playlist_name:
                return True, pl

        pl_body = self._get_playlist_create_body(playlist_name, channel_id=channel_id)

        try:
            pl_snippet = service.playlists().insert(body=pl_body, part='snippet, status').execute()
        except Exception as e:
            return False, e

        return True, pl_snippet

    @credentials_required
    def list_tracks_in_playlist(self, playlist):
        service = self.get_wrapped_service()

        video_ids = set()
        playlist_items_list_request = service.playlistItems().list(part='snippet', playlistId=playlist.service_id, maxResults=50)
        while playlist_items_list_request:
            playlist_items_list_response = playlist_items_list_request.execute()
            for item in playlist_items_list_response['items']:
                video_ids.add(item['snippet']['resourceId']['videoId'])

            playlist_items_list_request = service.playlistItems().list_next(playlist_items_list_request, playlist_items_list_response)

        return video_ids

    @credentials_required
    def add_track_to_playlist_by_track_id(self, playlist, track_id):
        service = self.get_wrapped_service()
        resource_body = {
            'kind': 'youtube#playlistItem',
            'snippet': {
                'playlistId': playlist.service_id,
                'resourceId': {
                    'kind': 'youtube#video',
                    'videoId': track_id,
                }
            }
        }

        # let exceptions bubble up
        resp = service.playlistItems().insert(part='snippet', body=resource_body).execute()
        self.tracks_in_playlist[playlist.service_id].add(track_id)

        return True, resp['snippet']['title']

    def add_links_to_playlist(self, playlist, links):
        return_messages = []
        for link in links:
            if 'yout' in link:
                return_messages.append(self.add_link_to_playlist(playlist, link))
            else:
                # TODO: do this
                continue

        return return_messages


class Spotify(ServiceBase):
    SCOPE = 'playlist-modify-private playlist-modify-public'
    NAME = 'Spotify'

    def __init__(self, *args, **kwargs):
        super(Spotify, self).__init__(*args, **kwargs)
        self.user_info = None
        self.track_info = {}

    @classmethod
    def get_flow(cls, state=None):
        return SpotipyDBWrapper(client_id=SPOTIFY_CLIENT_ID,
                                client_secret=SPOTIFY_CLIENT_SECRET,
                                redirect_uri=SPOTIFY_REDIRECT_URI,
                                scope=cls.SCOPE,
                                state=state,
                                )

    @classmethod
    def get_auth_uri(cls, state=None):
        flow = cls.get_flow(state=state)
        return flow.get_authorize_url()

    @classmethod
    def exchange(cls, code, state):
        flow = cls.get_flow(state=state)
        creds = flow.get_access_token(code=code)
        return SimpleJSONWrapper(data_dict=creds)

    def get_track_id(self, link):
        return strip_spotify_track_id(link)

    @credentials_required
    def get_wrapped_service(self):
        if self.service:
            return self.service
        credentials_manager = SpotipyClientCredentialsManager(credentials=self.credentials)
        return Spotipy(client_credentials_manager=credentials_manager)

    @credentials_required
    def get_user_info_from_spotify(self):
        if self.user_info:
            return self.user_info

        service = self.get_wrapped_service()

        self.user_info = service.me()

        if not self.user_info:
            raise Exception("No such user")

        return self.user_info

    @credentials_required
    def get_track_info(self, track_id):
        track_info = self.track_info.get(track_id, None)
        if track_info:
            return track_info

        service = self.get_wrapped_service()

        track_info = service.tracks(tracks=[track_id])
        if not track_info:
            return None

        track_info = track_info['tracks'][0]

        self.track_info[track_id] = track_info
        return track_info

    @credentials_required
    def create_playlist(self, playlist_name, user_id):
        service = self.get_wrapped_service()

        spotify_user_info = self.get_user_info_from_spotify()
        if not spotify_user_info:
            return False, "Could not find info for this user"

        spotify_user_id = spotify_user_info['id']
        for pl in self.list_playlists():
            if pl['name'] == playlist_name:
                return True, pl

        playlist = service.user_playlist_create(user=spotify_user_id, name=playlist_name)
        return True, playlist

    @credentials_required
    def list_playlists(self):
        service = self.get_wrapped_service()

        spotify_user_info = self.get_user_info_from_spotify()
        if not spotify_user_info:
            return []

        spotify_user_id = spotify_user_info['id']
        playlist_results = service.user_playlists(user=spotify_user_id)
        playlists = []
        while playlist_results:
            playlists.extend(playlist_results['items'])
            playlist_results = service.next(playlist_results)

        return playlists

    @credentials_required
    def list_tracks_in_playlist(self, playlist):
        service = self.get_wrapped_service()

        tracks_request = service.user_playlist_tracks(user=self.get_user_info_from_spotify()['id'],
                                                      playlist_id=playlist.service_id)
        tracks = set()
        while tracks_request:
            tracks = tracks|set(tracks_request['items'])
            tracks_request = service.next(tracks_request)

        return tracks

    @credentials_required
    def add_track_to_playlist_by_track_id(self, playlist, track_id):
        service = self.get_wrapped_service()

        try:
            resp = service.user_playlist_add_tracks(user=self.get_user_info_from_spotify()['id'],
                                                    playlist_id=playlist.service_id,
                                                    tracks=[track_id])
        except SpotifyException as e:
            return False, e

        track_info = self.get_track_info(track_id=track_id)
        if not resp['snapshot_id']:
            return False, "Unable to add %s to %s" % (track_info['name'], playlist.name)

        self.tracks_in_playlist[playlist.service_id].add(track_id)

        artist_names = [artist['name'] for artist in track_info['artists']]

        return True, "%s - %s" % (track_info['name'], ", ".join(artist_names))

    @credentials_required
    def add_links_to_playlist(self, playlist, links):
        return_messages = []

        for link in links:
            if 'spotify' in link:
                return_messages.append(self.add_link_to_playlist(playlist=playlist, link=link))
            else:
                # TODO
                continue

        return return_messages


class GMusic(ServiceBase):
    pass
