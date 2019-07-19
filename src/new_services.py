import abc
import json
import httplib2
import re
from functools import wraps
from fuzzywuzzy import fuzz

from apiclient.discovery import build
from oauth2client.client import OAuth2WebServerFlow
from spotipy import Spotify as Spotipy
from spotipy.client import SpotifyException

from .constants import BAD_WORDS, DUPLICATE_TRACK, InvalidEnumException, Platform
from .oauth_wrappers import SpotipyClientCredentialsManager, SpotipyDBWrapper
from settings import (
    SPOTIFY_CLIENT_ID,
    SPOTIFY_CLIENT_SECRET,
    SPOTIFY_REDIRECT_URI,
    YOUTUBE_REDIRECT_URI,
    YOUTUBE_CLIENT_ID,
    YOUTUBE_CLIENT_SECRET
)


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


class TrackInfo(object):
    def __init__(self, name, platform, raw_json=None, artists=None, track_id=None, link=None):
        self.name = name
        self.platform = platform
        self.raw_json = raw_json  # NOTE: for youtube responses, this means raw['snippet']
        self.artists = artists
        self.track_id = track_id
        self.link = link

    def artists_display_name(self):
        if self.artists:
            if isinstance(self.artists, list):
                return ", ".join(self.artists)
            else:
                return ", ".join(self.artists.split(' '))

        return ''

    def artists_for_search(self):
        if self.platform is Platform.YOUTUBE:
            return ''

        if not self.artists:
            return ''

        if isinstance(self.artists, list):
            return " ".join(self.artists)

        return self.artists

    def track_name_for_comparison(self):
        if self.artists:
            return ("%s %s" % (self.name, self.artists_for_search())).strip()

        return self.name

    def get_track_name(self):
        if self.artists:
            return "%s - %s" % (self.name, self.artists_display_name())

        return self.name

    def description(self):
        if self.raw_json:
            return self.raw_json.get('description', '')

        return ''

    def channel_title(self):
        if self.raw_json:
            self.raw_json.get('channelTitle', '')

        return ''

    def track_open_url(self):
        if self.link:
            return self.link
        
        if self.platform is Platform.YOUTUBE:
            return "https://www.youtube.com/watch?v=%s" % self.track_id
        elif self.platform is Platform.SPOTIFY:
            return "https://open.spotify.com/track/%s" % self.track_id
        else:
            return None

    def track_image_url(self):
        if not self.raw_json:
            return None
    
        if self.platform is Platform.YOUTUBE:
            return self.raw_json.get('thumbnails', {}).get('default')
        elif self.platform is Platform.SPOTIFY:
            images = self.raw_json.get('images')
            if not images:
                return None
            
            return min(images, key=lambda im: im['height']).get('url', None)
        else:
            return None


    def sanitized_track_name(self):
        new_title = re.sub(r"[|&'_-]", "", self.name)
        new_title = re.sub(r'\([^)]*\)', '', new_title)
        new_title = re.sub(r'\[[^]]*\]', '', new_title)
        # take out multiple spaces
        new_title = ' '.join(new_title.split())

        for word in BAD_WORDS:
            replacer = re.compile("\\b%s\\b" % word, re.IGNORECASE)
            new_title = replacer.sub('', new_title)
        return new_title


class ServiceFactory(object):
    @classmethod
    def from_string(cls, string):
        if string.lower()[0] == 'y':
            return YoutubeService
        elif string.lower()[0] == 's':
            return SpotifyService
        else:
            raise Exception("Invalid platform")

    @classmethod
    def from_link(self, link):
        if 'yout' in link:
            return YoutubeService
        elif 'spotify' in link:
            return SpotifyService
        else:
            return None

    @classmethod
    def from_enum(cls, enum):
        if enum is Platform.YOUTUBE:
            return YoutubeService
        elif enum is Platform.SPOTIFY:
            return SpotifyService
        else:
            raise InvalidEnumException


class ServiceBase(object, metaclass=abc.ABCMeta):
    def __init__(self, credentials, client=None):
        self.credentials = credentials
        self.client = client
    
    @abc.abstractclassmethod
    def get_flow(cls):
        raise NotImplementedError()

    @abc.abstractclassmethod
    def get_auth_uri(cls, state=None):
        raise NotImplementedError()

    @abc.abstractclassmethod
    def exchange(cls, code, state):
        raise NotImplementedError()

    @abc.abstractmethod
    def get_wrapped_client(self):
        raise NotImplementedError()

    @abc.abstractmethod
    def get_track_info_from_link(self, link):
        raise NotImplementedError()

    @abc.abstractmethod
    def get_track_ids_in_playlist(self, playlist, track_id=None):
        raise NotImplementedError()

    @abc.abstractmethod
    def is_track_in_playlist(self, track_info, playlist):
        raise NotImplementedError()
    
    @abc.abstractmethod
    def add_track_to_playlist(self, track_info, playlist):
        raise NotImplementedError()
    
    @abc.abstractmethod
    def fuzzy_search_for_track(self, track_info):
        raise NotImplementedError()

    @abc.abstractmethod
    def create_playlist(self, playlist_name):
        raise NotImplementedError()


class YoutubeService(ServiceBase):
    SCOPE = 'https://www.googleapis.com/auth/youtube'
    API_SERVICE_NAME = "youtube"
    API_VERSION = "v3"
    NAME = 'Youtube'

    @classmethod
    def get_flow(cls):
        return OAuth2WebServerFlow(
            client_id=YOUTUBE_CLIENT_ID,
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

    @credentials_required
    def get_wrapped_client(self):
        if self.client:
            return self.client

        http_auth = self.credentials.authorize(httplib2.Http())
        return build(self.API_SERVICE_NAME, self.API_VERSION, http=http_auth)
    
    def get_track_info_from_link(self, link):
        if 'yout' not in link:
            # TODO
            return False
        
        video_id = None
        if "v=" in link:
            link.split('?')
            for param in link.split('&'):
                if 'v=' in param:
                    video_id = param.split('=')[1]
        else:
            # mobile video share
            # TODO: what is all this dumbass link splitting?
            link_parts = link.split()
            link = [p for p in link_parts if 'yout' in p]
            if not link:
                return None
            video_id = link[0].split('be/')[1]

        client = self.get_wrapped_client()
        resp = client.videos().list(part='snippet', id=video_id)
        items = resp.get('items', {})
        if not items or len(items) > 1:
            # TODO: what do here?
            return False
        
        track = items[0]
        
        return TrackInfo(
            track_id=video_id,
            platform=Platform.YOUTUBE,
            name=track['snippet']['title'],
            raw_json=track['snippet']
        )

    def get_track_ids_in_playlist(self, playlist, track_id=None, **kwargs):
        client = self.get_wrapped_client()

        list_kwargs = {
            'part': 'id',
            'playlistId': playlist.platform_id,
            'maxResults': 50
        }
        if track_id:
            list_kwargs['videoId'] = track_id
        
        list_kwargs.update(**kwargs)

        track_ids = set()
        playlist_items_list_request = client.playlistItems().list(**list_kwargs)
        while playlist_items_list_request:
            playlist_items_list_response = playlist_items_list_request.execute()
            track_ids = track_ids.union({item['id'] for item in playlist_items_list_response['items']})

            playlist_items_list_request = client.playlistItems().list_next(playlist_items_list_request, playlist_items_list_response)

        return track_ids

    def is_track_in_playlist(self, track_info, playlist):
        return track_info.track_id in self.get_track_ids_in_playlist(playlist=playlist, track_id=track_info.track_id)
    
    def add_track_to_playlist(self, track_info, playlist):
        client = self.get_wrapped_client()

        if self.is_track_in_playlist(track_info=track_info, playlist=playlist):
            return False, DUPLICATE_TRACK

        resource_body = {
            'kind': 'youtube#playlistItem',
            'snippet': {
                'playlistId': playlist.platform_id,
                'resourceId': {
                    'kind': 'youtube#video',
                    'videoId': track_info.track_id,
                }
            }
        }

        try:
            resp = client.playlistItems().insert(part='snippet', body=resource_body).execute()
        except Exception as e:
            # TODO: better exception handling
            return False, str(e)
        
        return True, None
    
    def fuzzy_search_for_track(self, track_info):
        client = self.get_wrapped_client()
        search_kwargs = {
            'part': 'snippet',
            'maxResults': 10,
            'type': 'video'
        }

        try:
            search_results = client.search().list(q=track_info.get_track_name(), **search_kwargs).execute()
        except Exception as e:
            # TODO: better exception handling
            return None

        items = search_results.get('items', None)
        if not items:
            return None

        best_result = (None, 0)
        for item in items:
            contender = fuzz.token_set_ratio(track_info.track_name_for_comparison(), item['snippet']['title'])
            if contender > best_result[1] and contender > 85:
                best_result = (item, contender)

        if not best_result[0]:
            return None

        return TrackInfo(
            track_id=best_result[0]['id']['videoId'],
            name=best_result[0]['snippet']['title'],
            platform=Platform.YOUTUBE,
            raw_json=best_result[0]['snippet']
        )

    def create_playlist(self, playlist_name):
        raise NotImplementedError()


class SpotifyService(ServiceBase):
    SCOPE = 'playlist-modify-private playlist-modify-public'
    NAME = 'Spotify'

    def __init__(self, *args, **kwargs):
        user_info = kwargs.pop('user_info')
        
        super(SpotifyService, self).__init__(*args, **kwargs)

        self.user_info = user_info

    @classmethod
    def get_flow(cls, state=None):
        return SpotipyDBWrapper(
            client_id=SPOTIFY_CLIENT_ID,
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


    @credentials_required
    def get_wrapped_client(self):
        if self.client:
            return self.client
        
        credentials_manager = SpotipyClientCredentialsManager(credentials=self.credentials)
        
        client = Spotipy(client_credentials_manager=credentials_manager)
        self.client = client
        return client

    # save an api call by caching user info
    def get_user_info(self):
        if self.user_info:
            return self.user_info
        
        client = self.get_wrapped_client()
        user_info = client.me()
        self.user_info = user_info
        
        return user_info

    def get_track_info_from_link(self, link):
        track_id = None
        if link.find('spotify:track') != -1:
            track_id = link.split(':')[-1]
        else:
            track_id = link.split('/')[-1].split('?')[0]

        client = self.get_wrapped_client()
        try:
            track_info = client.track(track_id=track_id)['tracks'][0]
        except Exception as e:
            # TODO: better error handling
            return None

        return TrackInfo(
            track_id=track_id,
            name=track_info['name'],
            platform=Platform.SPOTIFY,
            raw_json=track_info,
            artists=[a['name'] for a in track_info['artists']]
        )
    
    def get_track_ids_in_playlist(self, playlist, track_id=None):
        client = self.get_wrapped_client()

        tracks_request = client.user_playlist_tracks(
            user=self.get_user_info()['id'],
            playlist_id=playlist.platform_id
        )

        track_ids = set()
        tracks_request = client.next(tracks_request)
        while tracks_request:
            track_ids= track_ids.union({t['track']['id'] for t in tracks_request['items']})

            tracks_request = client.next(tracks_request)

        return track_ids

    def is_track_in_playlist(self, track_info, playlist):
        return track_info.track_id in self.get_track_ids_in_playlist(playlist=playlist)
    
    def add_track_to_playlist(self, track_info, playlist):
        client = self.get_wrapped_client()
        
        try:
            resp = client.user_playlist_add_tracks(
                user=self.get_user_info()['id'],
                playlist_id=playlist.client_id,
                tracks=[track_info.track_id]
            )
        except SpotifyException as e:
            return False, e
        except Exception as e:
            # TODO: better error handling
            return False, e

        if not resp['snapshot_id']:
            return False, "Unable to add %s to %s" % (track_info['name'], playlist.name)

        return True, None
    
    def fuzzy_search_for_track(self, track_info):
        client = self.get_wrapped_client()
        search_kwargs = {
            'market': 'US',
            'type': 'track',
            'limit': 50
        }
        
        search_string = track_info.sanitized_track_name()
        if track_info.platform is Platform.SPOTIFY:
            search_string += " artist:%s" % track_info.artists_for_search()
        
        results = client.search(q=search_string, **search_kwargs)
        if not results:
            return None
        if not results.get('tracks', {}).get('items'):
            return None

        items = results['tracks']['items']
        best_score_so_far = 0
        contenders = []
        target = track_info.track_name_for_comparison()
        # TODO: break this out into helper
        """
        STAGE 1: a token_set_ratio
        
        Check if the given name and artist combo at least form a set of the results
        """
        for item in items:
            contender_name = item['name']
            contender_artist = " ".join(a['name'] for a in item['artists'])
            # using set
            contender = fuzz.token_set_ratio(target.lower(), ("%s %s" % (contender_name, contender_artist)).lower())
            if contender >= best_score_so_far and contender > 75:
                best_score_so_far = contender
                contenders.append(item)

        if not contenders:
            return None

        if len(contenders) == 1:
            winner = contenders[0]
            return TrackInfo(
                platform=Platform.SPOTIFY,
                raw_json=winner,
                name=winner['name'],
                artists=[a['name'] for a in winner['artists']],
                track_id=winner['id']
            )

        """
        STAGE 2: token_sort_ratio
        
        If multiple contenders pass the token_set_ratio criteria, try a token_sort_ratio.
        How many transformations are necessary to change the source string to the target string?
        """
        best_sort_score_so_far = 0
        sort_contenders = []
        for contender in contenders:
            contender_name = contender['name']
            contender_artist = " ".join(a['name'] for a in contender['artists'])
            # using sort
            sort_score = fuzz.token_sort_ratio(
                target.lower(), ("%s %s" % (contender_name, contender_artist)).lower())
            if sort_score >= best_sort_score_so_far and sort_score > 65:
                contender['sort_score'] = sort_score
                best_sort_score_so_far = sort_score
                sort_contenders.append(contender)

        highest_sort_score = max(sort_contenders, key=lambda b: b['sort_score'])['sort_score']
        best_contenders = [c for c in sort_contenders if c['sort_score'] == highest_sort_score]

        # If we've been passed a Spotify track, then there's no description to check for artists,
        # so just pick the most popular track
        if track_info.platform is Platform.SPOTIFY:
            if len(contenders) == 1:
                winner = best_contenders[0]
            else:
                winner = max(contenders, key=lambda c: c['popularity'])

            return TrackInfo(
                name=winner['name'],
                artists=[a['name'] for a in winner['artists']],
                track_id=winner['id'],
                platform=Platform.SPOTIFY,
                raw_json=winner
            )

        """
        STAGE 3:
        
        Multiple contenders have passed the token_sort_score check. And the track_info came from a Youtube track
            
        We have to get craftier, 
        A contender is a spotify api response, track_info is a youtube TrackInfo object
        Check the channelTitle and description for mentions of the artist name
        """
        best_results_with_artist = []
        best_score_so_far_with_artist = 0
        original_description = track_info.description().lower()
        for contender in contenders:
            """
            if we're here, it means comparing to track title to the artists from the spotify response didn't help differentiate.
            To decide:
            1. see if we can find the artist(s) name(s) in the description of the video; add +10 to the search score for that
            2. see if we can find the artist(s) name(s) in the channel title (e.g., Maroon 5 Official); add +25 for that
            3. if there's still a tie, take the most popular one
            """
            current_score = 0
            for a in contender['artists']:
                if a['name'].lower() in original_description:
                    current_score += 10

                if a['name'].lower() in track_info.channel_title().lower():
                    current_score += 25

            if current_score > 0 and current_score >= best_score_so_far_with_artist:
                contender['with_artist_score'] = current_score
                best_results_with_artist.append(contender)

        if best_results_with_artist:
            highest_best_result_with_artist_score = max(
                best_results_with_artist, key=lambda b: b['with_artist_score'])['with_artist_score']
            winner = max([
                c for c in best_results_with_artist if c['with_artist_score'] >= highest_best_result_with_artist_score],
                key=lambda bra: bra['popularity']
            )
        else:
            winner = max(contenders, key=lambda c: c['popularity'])

        if not winner:
            return None

        return TrackInfo(
            raw_json=winner,
            name=winner['name'],
            artists=[a['name'] for a in winner['artists']],
            track_id=winner['id'],
            platform=Platform.SPOTIFY
        )


    def create_playlist(self, playlist_name):
        raise NotImplementedError()
