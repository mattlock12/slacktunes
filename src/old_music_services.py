import json
import httplib2
import re
from functools import wraps
from fuzzywuzzy import fuzz

from apiclient.discovery import build
from oauth2client.client import OAuth2WebServerFlow
from spotipy import Spotify as Spotipy
from spotipy.client import SpotifyException

from settings import YOUTUBE_CLIENT_ID, YOUTUBE_CLIENT_SECRET, YOUTUBE_REDIRECT_URI, SPOTIFY_CLIENT_ID, SPOTIFY_CLIENT_SECRET, SPOTIFY_REDIRECT_URI

from .constants import BAD_WORDS, InvalidEnumException, Platform
from .oauth_wrappers import SpotipyClientCredentialsManager, SpotipyDBWrapper


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

    def track_name_for_display(self):
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
        self.track_info = {}
        self.tracks_in_playlist = {}

    @classmethod
    def from_string(cls, string):
        if string.lower()[0] == 'y':
            return Youtube
        elif string.lower()[0] == 's':
            return Spotify
        else:
            raise Exception("Invalid service")

    @classmethod
    def from_link(self, link):
        if 'yout' in link:
            return Youtube
        elif 'spotify' in link:
            return Spotify
        else:
            return None

    @classmethod
    def from_enum(cls, enum):
        if enum is Platform.YOUTUBE:
            return Youtube
        elif enum is Platform.SPOTIFY:
            return Spotify
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
        # should never happen but this is not how to handle it anyway
        if not self.is_same_platform_link(link):
            return False, None, ""

        track_id = self.get_track_id(link)
        if not track_id:
            return False, None, "Could not parse video id"

        return self.add_track_to_playlist_by_track_id(playlist=playlist, track_id=track_id)

    @credentials_required
    def get_track_info_from_link(self, link):
        raise NotImplementedError

    @credentials_required
    def add_track_to_playlist_by_track_id(self, playlist, track_id):
        raise NotImplementedError

    @credentials_required
    def get_native_track_info_from_track_info(self, track_info, is_spotify=False):
        raise NotImplementedError

    @credentials_required
    def search(self, search_string, *args, **kwargs):
        raise NotImplementedError

    @credentials_required
    def add_manual_track_to_playlist(self, playlist, track_name, artist):
        ti = TrackInfo(name=track_name, artists=artist)
        native_track_info = self.get_native_track_info_from_track_info(
            track_info=ti,
            is_spotify=playlist.platform == Platform.SPOTIFY
        )
        if not native_track_info:
            return False, None, 'No track info found'
        return self.add_track_to_playlist_by_track_id(track_id=native_track_info.track_id, playlist=playlist)


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
            "description": "slacktunes created playlist! Check out https://slacktunes.me",
            "tags": ["slacktunes", ],
            "channelId": channel_id,
            "title": playlist_name,
            },
        }

    def is_same_platform_link(self, link):
        return 'yout' in link

    def get_track_id(self, link):
        video_id = None
        if "v=" not in link:
            # mobile video share
            link_parts = link.split()
            link = [p for p in link_parts if 'yout' in p]
            if not link:
                return None

            return link[0].split('be/')[1]

        link.split('?')
        for param in link.split('&'):
            if 'v=' in param:
                video_id = param.split('=')[1]
                break
        return video_id

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
    def create_playlist(self, playlist_name):
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
    def list_tracks_in_playlist(self, playlist, track_id=None):
        service = self.get_wrapped_service()

        list_kwargs = {
            'part': 'snippet',
            'playlistId': playlist.platform_id,
            'maxResults': 50
        }
        if track_id:
            list_kwargs['videoId'] = track_id

        tracks = []
        playlist_items_list_request = service.playlistItems().list(**list_kwargs)
        while playlist_items_list_request:
            playlist_items_list_response = playlist_items_list_request.execute()
            tracks += [
                TrackInfo(
                    track_id=item['snippet']['resourceId']['videoId'],
                    name=item['snippet']['title']
                )
                for item in playlist_items_list_response['items']
            ]

            playlist_items_list_request = service.playlistItems().list_next(playlist_items_list_request, playlist_items_list_response)

        return tracks

    @credentials_required
    def add_track_to_playlist_by_track_id(self, playlist, track_id):
        service = self.get_wrapped_service()

        # optimization for multiple adds
        cached_tracks = self.tracks_in_playlist.get(playlist.platform_id)
        if cached_tracks and track_id in set(ct.track_id for ct in cached_tracks):
            return False, [t for t in cached_tracks if t.track_id == track_id][0], "Already in playlist"

        # check the api, the ultimate source of truth
        existing_tracks = self.list_tracks_in_playlist(playlist=playlist, track_id=track_id)
        if existing_tracks:
            return False, existing_tracks[0], "Already in playlist"

        resource_body = {
            'kind': 'youtube#playlistItem',
            'snippet': {
                'playlistId': playlist.platform_id,
                'resourceId': {
                    'kind': 'youtube#video',
                    'videoId': track_id,
                }
            }
        }

        # let exceptions bubble up
        resp = service.playlistItems().insert(part='snippet', body=resource_body).execute()
        track_info = TrackInfo(raw_json=resp['snippet'], track_id=track_id, name=resp['snippet']['title'])

        return True, track_info, ''

    @credentials_required
    def add_links_to_playlist(self, playlist, links):
        return_messages = []

        # let's say a large playlist is ~1000 songs; get a list of all tracks in playlist if it'll take more than
        # 10 individual calls to get a list of all track_ids
        if len(links) > 10:
            self.tracks_in_playlist[playlist.platform_id] = self.list_tracks_in_playlist(playlist=playlist)

        for link in links:
            if 'yout' in link:
                return_messages.append(self.add_link_to_playlist(playlist, link))
            else:
                # TODO: do this
                continue

        return return_messages

    @credentials_required
    def get_track_info_from_link(self, link):
        service = self.get_wrapped_service()
        track_id = self.get_track_id(link)
        results = service.videos().list(part='snippet', id=track_id).execute()

        # be safe
        if not results:
            return None
        if not results['items']:
            return None
        if not results['items'][0]:
            return None
        if not results['items'][0].get('snippet', {}).get('title'):
            return None

        return TrackInfo(
            raw_json=results['items'][0]['snippet'], name=results['items'][0]['snippet']['title'], track_id=track_id)

    @credentials_required
    def search(self, search_string, **kwargs):
        service = self.get_wrapped_service()
        search_kwargs = {
            'part': 'snippet',
            'maxResults': 10,
            'type': 'video'
        }
        search_kwargs.update(kwargs)
        return service.search().list(q=search_string, **search_kwargs).execute()

    def get_native_track_info_from_track_info(self, track_info, is_spotify=False):
        results = self.search(search_string=track_info.track_name_for_display())
        if not results['items']:
            return None

        items = results['items']
        if not items:
            return None

        best_result = (None, 0)
        for item in items:
            contender = fuzz.token_set_ratio(track_info.track_name_for_display(), item['snippet']['title'])
            if contender > best_result[1] and contender > 85:
                best_result = (item, contender)

        if not best_result[0]:
            return None

        return TrackInfo(
            raw_json=best_result[0]['snippet'],
            name=best_result[0]['snippet']['title'],
            track_id=best_result[0]['id']['videoId'])


class Spotify(ServiceBase):
    SCOPE = 'playlist-modify-private playlist-modify-public'
    NAME = 'Spotify'

    def __init__(self, *args, **kwargs):
        super(Spotify, self).__init__(*args, **kwargs)
        self.user_info = None

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
        if link.find('spotify:track') != -1:
            return link.split(':')[-1]

        return link.split('/')[-1].split('?')[0]

    def is_same_platform_link(self, link):
        return 'spotify' in link

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

        return TrackInfo(
            raw_json=track_info,
            track_id=track_id,
            name=track_info['name'],
            artists=[a['name'] for a in track_info['artists']]
        )

    @credentials_required
    def create_playlist(self, playlist_name):
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
                                                      playlist_id=playlist.platform_id)
        tracks = []
        while tracks_request:
            tracks += [
                TrackInfo(
                    raw_json=t,
                    track_id=t['track']['id'],
                    name=t['track']['name'],
                    artists=[a['name'] for a in t['track']['artists']]
                )
                for t in tracks_request['items']
            ]
            tracks_request = service.next(tracks_request)

        return tracks

    @credentials_required
    def get_track_info_from_link(self, link):
        return self.get_track_info(track_id=self.get_track_id(link))

    @credentials_required
    def search(self, search_string, **kwargs):
        service = self.get_wrapped_service()
        search_kwargs = {
            'market': 'US',
            'type': 'track',
            'limit': 50
        }
        search_kwargs.update(kwargs)
        try:
            return service.search(q=search_string, **search_kwargs)
        except SpotifyException:
            return None

    def get_native_track_info_from_track_info(self, track_info, is_spotify=False):
        search_str = track_info.sanitized_track_name()
        track_results = None

        if is_spotify:
            results =  self.search(
                "track:%s artist:%s" % (track_info.sanitized_track_name(), track_info.artists_for_search()))
        else:
            track_results = self.search('track:%s' % search_str)
            results = self.search(search_str)


        if not results:
            return None
        if not results.get('tracks'):
            return None
        if not results['tracks'].get('items'):
            return None

        items = results['tracks']['items']
        if track_results:
            items += track_results.get('tracks', {}).get('items', [])

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

        if is_spotify:
            highest_sort_score = max(sort_contenders, key=lambda b: b['sort_score'])['sort_score']
            best_contenders = [c for c in sort_contenders if c['sort_score'] >= highest_sort_score]

            if len(contenders) == 1:
                winner = best_contenders[0]
            else:
                winner = max(contenders, key=lambda c: c['popularity'])

            return TrackInfo(
                raw_json=winner,
                name=winner['name'],
                artists=[a['name'] for a in winner['artists']],
                track_id=winner['id']
            )

        """
        STAGE 3:
        
        Multiple contenders have passed the token_sort_score check. And the source was a Youtube track
            
        We have to get craftier, 
        A contender is a spotify api response, track_info is a youtube TrackInfo object
        Check the channelTitle and description for mentions of the artist name
        """
        best_results_with_artist = []
        best_score_so_far_with_artist = 0
        original_description = track_info.description().lower()
        for contender in contenders:
            """
            if we're here, it means the artists from the spotify res contender string didn't help differentiate
            To decide:
            1. see if we can find the artist(s) name(s) in the description of the video; add +10 points for each find
            2. if there's still a tie, take the most popular one
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
            track_id=winner['id']
        )

    @credentials_required
    def add_track_to_playlist_by_track_id(self, playlist, track_id):
        service = self.get_wrapped_service()

        existing_tracks = self.tracks_in_playlist.get(playlist.platform_id, None)
        if not existing_tracks:
            existing_tracks = self.tracks_in_playlist[playlist.platform_id] = self.list_tracks_in_playlist(playlist)

        existing_track_ids = set(t.track_id for t in existing_tracks)
        if track_id in existing_track_ids:
            return False, [et for et in existing_tracks if et.track_id == track_id][0], "Already in playlist"

        try:
            resp = service.user_playlist_add_tracks(user=self.get_user_info_from_spotify()['id'],
                                                    playlist_id=playlist.platform_id,
                                                    tracks=[track_id])
        except SpotifyException as e:
            return False, None, e

        track_info = self.get_track_info(track_id=track_id)
        if not resp['snapshot_id']:
            return False, None, "Unable to add %s to %s" % (track_info['name'], playlist.name)

        self.tracks_in_playlist[playlist.platform_id].append(track_info)

        return True, track_info, ''

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
