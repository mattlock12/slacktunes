from json_fakes import (
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


class FakeYoutubeClient(object):
    def __init__(self, *args, **kwargs):
        expected_responses = kwargs.pop('expected_responses', {})

        super(FakeYoutubeClient, self).__init__(*args, **kwargs)

        self.expected_responses = expected_responses

    def videos(self):
        expected_response = self.expected_responses.get('videos_list')
        
        class FakeVideosList(object):
            @classmethod
            def list(cls, part, id, *args, **kwargs):
                if expected_response:
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
                if expected_list_response:
                    return expected_list_response
                
                return YOUTUBE_PLAYLIST_ITEMS_LIST_RESPONSE

            @classmethod
            def list_next(cls, playlist_items_list_request, playlist_items_list_response):
                if expected_next_response:
                    return expected_next_response
                
                # Pretend we never get paginated results
                return None

            @classmethod
            def insert(cls, part, body):
                class FakeExecutor(object):
                    @classmethod
                    def execute(kls):
                        if expected_insert_response:
                            return expected_insert_response

                        # We don't check for any response except an error
                        return True
                    
                return FakeExecutor
        
        return FakePlaylistItems

    def search(self):
        expected_search_response = self.expected_responses.get('search')
        
        class FakeSearch(object):
            @classmethod
            def list(cls, q, **kwargs):
                if expected_search_response:
                    return expected_search_response
                
                return YOTUBE_SEARCH_LIST_RESPONSE

        return FakeSearch

            
class FakeSpotifyClient(object):
    def __init__(self, *args, **kwargs):
        expected_responses = kwargs.pop('expected_responses', {})

        super(FakeSpotifyClient, self).__init__(*args, **kwargs)

        self.expected_responses = expected_responses

    def me(self):
        expected_response = self.expected_responses.get('me')
        if expected_response:
            return expected_response
        
        return SPOTIFY_USER_RESP

    def track(self, track_id):
        expected_response = self.expected_responses.get('track')
        if expected_response:
            return expected_response

        return SPOTIFY_TRACK_RESP
    
    def user_playlist_tracks(self, user, playlist_id):
        expected_response = self.expected_responses.get('user_playlist_tracks')
        if expected_response:
            return expected_response

        return SPOTIFY_PLAYLIST_TRACKS_RESP

    def user_playlist_add_tracks(self, user, playlist_id, tracks):
        expected_response = self.expected_responses.get('user_playlist_add_tracks')
        if expected_response:
            return expected_response

        return SPOTIFY_ADD_TRACK_RESPONSE
    
    def search(self, q, **kwargs):
        expected_response = self.expected_responses.get('search')
        if expected_response:
            return expected_response

        return SPOTIFY_SEARCH_RESULTS

    def next(self, tracks_request):
        expected_response = self.expected_responses.get('next')
        if expected_response:
            return expected_response

        # Pretend we never get paginated responses
        return None