from .json_fakes import (
    SPOTIFY_ADD_TRACK_RESPONSE,
    SPOTIFY_PLAYLIST_TRACKS_RESP,
    SPOTIFY_SEARCH_RESULTS,
    SPOTIFY_TRACK_RESP,
    SPOTIFY_USER_RESP,
    YOUTUBE_PLAYLIST_ITEMS_LIST_RESPONSE,
    YOTUBE_SEARCH_LIST_RESPONSE,
    YOUTUBE_VIDEOS_LIST_SINGLE_RESPONSE,
)
from .new_services import ServiceBase


def get_yerself_an_executor(expected, default):
    class FakeExecutor(object):
        @classmethod
        def execute(cls):
            if expected:
                if callable(expected):
                    expected()
                return expected
            
            return default

    return FakeExecutor

class FakeYoutubeClient(object):
    def __init__(self, *args, **kwargs):
        expected_responses = kwargs.pop('expected_responses', {})

        self.expected_responses = expected_responses
        self.insert_calls = []

    def videos(self):
        expected_response = self.expected_responses.get('videos_list')
        
        class FakeVideosList(object):
            @classmethod
            def list(cls, part, id, *args, **kwargs):
                if expected_response:
                    # might be an exception
                    if callable(expected_response):
                        expected_response()
                    return expected_response
                
                return YOUTUBE_VIDEOS_LIST_SINGLE_RESPONSE

        return FakeVideosList

    def playlistItems(self):
        expected_list_response = self.expected_responses.get('playlistItems_list')
        expected_next_response = self.expected_responses.get('playlistItems_next')
        expected_insert_response = self.expected_responses.get('playlistItem_insert')

        class FakePlaylistItems(object):
            
            @classmethod
            def list(cls, **kwargs):
                return get_yerself_an_executor(
                    expected=expected_list_response,
                    default=YOUTUBE_PLAYLIST_ITEMS_LIST_RESPONSE
                )

            @classmethod
            def list_next(cls, playlist_items_list_request, playlist_items_list_response):
                if expected_next_response:
                    if callable(expected_next_response):
                        expected_next_response()
                    return expected_next_response
                
                # let's pretend we never get paginated responses
                return None

            @classmethod
            def insert(cls, part, body):
                self.insert_calls.append(body)
                
                return get_yerself_an_executor(
                    expected=expected_insert_response,
                    default=True
                )
        
        return FakePlaylistItems

    def search(self):
        expected_search_response = self.expected_responses.get('search')
        
        class FakeSearch(object):
            @classmethod
            def list(cls, q, **kwargs):
                return get_yerself_an_executor(
                    expected=expected_search_response,
                    default=YOTUBE_SEARCH_LIST_RESPONSE
                )

        return FakeSearch

    def channels(self):
        expected_list_response = self.expected_responses.get('channels_list')

        class FakeList(object):
            @classmethod
            def list(cls):
                return get_yerself_an_executor(
                    expected=expected_list_response,
                    default={"items": [{"id": 123}]}
                )
                
        return FakeList

    def playlists(self):
        expected_list_response = self.expected_responses.get('playlists_list')
        expected_insert_response = self.expected_responses.get('playlists_insert')

        class FakePlaylists(object):
            @classmethod
            def list(cls, *args, **kwargs):
                return get_yerself_an_executor(
                    expected=expected_list_response,
                    default=[
                        {'snippet': {'title': 'Playlist1'}},
                        {'snippet': {'title': 'Playlist2'}},
                    ]
                )
        
            @classmethod
            def list_next(cls, *args, **kwargs):
                return get_yerself_an_executor(
                    expected=None,
                    default=None
                )
            
            @classmethod
            def insert(cls, body, part):
                title = body['snippet']['title']

                return get_yerself_an_executor(
                    expected=expected_insert_response,
                    default={
                        'id': 'abc123',
                        'snippet': {
                            'title': title
                        }
                    }
                )

        return FakePlaylists

            
class FakeSpotifyClient(object):
    def __init__(self, *args, **kwargs):
        expected_responses = kwargs.pop('expected_responses', {})
     
        self.nexted = False
        self.expected_responses = expected_responses
        self.add_track_calls = []

    def me(self):
        expected_response = self.expected_responses.get('me')
        if expected_response:
            # might be an exception
            if callable(expected_response):
                expected_response()
            return expected_response
        
        return SPOTIFY_USER_RESP

    def track(self, track_id):
        expected_response = self.expected_responses.get('track')
        if expected_response:
            # might be an exception
            if callable(expected_response):
                expected_response()
            return expected_response

        return SPOTIFY_TRACK_RESP
    
    def user_playlists(self, user):
        expected_response = self.expected_responses.get('user_playlists')
        if expected_response:
            if callable(expected_response):
                return expected_response
            return expected_response

        # TODO: improve once you have internet
        return [{'name': 'Playlist1'}, {'name': 'Playlist2'}]

    def user_playlist_create(self, user, name):
        expected_response = self.expected_responses.get('user_playlists')
        if expected_response:
            if callable(expected_response):
                return expected_response
            return expected_response
        
        return True
    
    def user_playlist_tracks(self, user, playlist_id):
        expected_response = self.expected_responses.get('user_playlist_tracks')
        if expected_response:
            # might be an exception
            if callable(expected_response):
                expected_response()
            return expected_response

        return SPOTIFY_PLAYLIST_TRACKS_RESP

    def user_playlist_add_tracks(self, user, playlist_id, tracks):
        expected_response = self.expected_responses.get('user_playlist_add_tracks')
        self.add_track_calls += tracks
        
        if expected_response:
            # might be an exception
            if callable(expected_response):
                expected_response()
            
            return expected_response

        return SPOTIFY_ADD_TRACK_RESPONSE
    
    def search(self, q, **kwargs):
        expected_response = self.expected_responses.get('search')
        if expected_response:
            # might be an exception
            if callable(expected_response):
                expected_response()
            return expected_response

        return SPOTIFY_SEARCH_RESULTS

    def next(self, tracks_request):
        expected_response = self.expected_responses.get('next')
        if expected_response:
            # might be an exception
            if callable(expected_response):
                expected_response()
            return expected_response

        # Pretend we never get paginated responses
        if self.nexted:
            return None

        self.nexted = True

        return SPOTIFY_PLAYLIST_TRACKS_RESP