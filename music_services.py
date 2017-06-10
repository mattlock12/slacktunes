import httplib2
from functools import wraps

from apiclient.discovery import build
from oauth2client.client import OAuth2WebServerFlow

from settings import YOUTUBE_CLIENT_ID, YOUTUBE_CLIENT_SECRET, YOUTUBE_REDIRECT_URI
from utils import strip_youtube_video_id


class NoCredentialsError(Exception):
    pass


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
        self.videos_in_playlists = {}


class Youtube(ServiceBase):
    SCOPE = 'https://www.googleapis.com/auth/youtube'
    API_SERVICE_NAME = "youtube"
    API_VERSION = "v3"

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
    def exchange(cls, code):
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
            return False, "Too many channels"

        channel_id = channels_response['items'][0]['id']

        existing_playlists = service.playlists().list(part='snippet', mine=True).execute()
        for pl in existing_playlists['items']:
            if pl['snippet']['title'] == playlist_name:
                return True, pl

        pl_body = self._get_playlist_create_body(playlist_name, channel_id=channel_id)

        try:
            pl_snippet = service.playlists().insert(body=pl_body, part='snippet, status').execute()
        except Exception as e:
            return False, e

        return True, pl_snippet

    @credentials_required
    def list_videos_in_playlist(self, playlist):
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
    def add_link_to_playlist(self, playlist, link):
        if not self.credentials:
            raise NoCredentialsError

        existing_video_ids = self.videos_in_playlists.get(playlist.service_id, set())
        if not existing_video_ids:
            existing_video_ids = self.videos_in_playlists[playlist.service_id] = self.list_videos_in_playlist(playlist)

        video_id = strip_youtube_video_id(link)
        if video_id in existing_video_ids:
            return False, "Already in playlist"

        service = self.get_wrapped_service()
        resource_body = {
            'kind': 'youtube#playlistItem',
            'snippet': {
                'playlistId': playlist.service_id,
                'resourceId': {
                    'kind': 'youtube#video',
                    'videoId': video_id,
                }
            }
        }
        resp = service.playlistItems().insert(part='snippet', body=resource_body).execute()
        existing_video_ids.add(video_id)
        self.videos_in_playlists[playlist.service_id] = existing_video_ids

        return True, resp

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
    pass


class GMusic(ServiceBase):
    pass
