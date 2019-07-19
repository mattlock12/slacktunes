import copy
import unittest

from fuzzywuzzy import fuzz

from .base import DatabaseTestBase
from src.constants import DUPLICATE_TRACK, Platform
from src.fakes import FakeSpotifyClient, FakeYoutubeClient
from src.json_fakes import (
    YOUTUBE_PLAYLIST_ITEMS_LIST_RESPONSE,
    YOTUBE_SEARCH_LIST_RESPONSE,
    YOUTUBE_VIDEOS_LIST_SINGLE_RESPONSE,    
)
from src.models import Playlist
from src.new_services import ServiceFactory, SpotifyService, TrackInfo, YoutubeService

YOUTUBE_LINK_WEB = "https://www.youtube.com/watch?v=XPpTgCho5ZA"
YOUTUBE_LINK_MOBILE = "https://youtu.be/XPpTgCho5ZA"
YOUTUBE_LINKS = [
    YOUTUBE_LINK_MOBILE,
    YOUTUBE_LINK_WEB
]

SPOTIFY_LINK_WEB = "https://open.spotify.com/track/6ECp64rv50XVz93WvxXMGF?si=lJluQIadSSaeutkEbIWquQ"
SPOTIFY_LINK_DESKTOP = "spotify:track:6ECp64rv50XVz93WvxXMGF"
SPOTIFY_LINKS = [
    SPOTIFY_LINK_DESKTOP,
    SPOTIFY_LINK_WEB
]

class TrackInfoTestCase(unittest.TestCase):
    def test_artists_display_name(self):
        pass

    def artists_for_search(self):
        pass

    def test_track_name_for_comparison(self):
        pass

    def test_get_track_name(self):
        pass

    def test_description(self):
        pass

    def test_channel_title(self):
        pass

    def test_track_open_url_youtube(self):
        pass

    def test_track_open_url_spotify(self):
        pass

    def test_track_image_url_youtube(self):
        pass
    
    def test_track_image_url_spotify(self):
        pass

    def sanitized_track_name(self):
        pass


class ServiceFactoryTestCase(unittest.TestCase):
    def test_from_string(self):
        for yt_string in ['y','Y']:
            self.assertEqual(
                ServiceFactory.from_string(yt_string),
                YoutubeService
            )

        for spotify_string in ['s', 'S']:
            self.assertEqual(
                ServiceFactory.from_string(spotify_string),
                SpotifyService
            )

    def test_from_link(self):
        for ylink in YOUTUBE_LINKS:
            self.assertEqual(
                ServiceFactory.from_link(ylink),
                YoutubeService
            )

        for slink in SPOTIFY_LINKS:
            self.assertEqual(
                ServiceFactory.from_link(slink),
                SpotifyService
            )

    def test_from_enum(self):
        self.assertEqual(
            ServiceFactory.from_enum(Platform.YOUTUBE),
            YoutubeService
        )

        self.assertEqual(
            ServiceFactory.from_enum(Platform.SPOTIFY),
            SpotifyService
        )


class YoutubeServiceTestCase(DatabaseTestBase):
    def setUp(self):
        super(YoutubeServiceTestCase, self).setUp()

        self.service = YoutubeService(credentials={'ok': True}, client=FakeYoutubeClient())
        self.playlist = Playlist(
            name='yt',
            channel_id='123',
            platform=Platform.YOUTUBE,
            platform_id='abc123',
            user_id=1
        )

        self.track_info = TrackInfo(
            name="Maroon 5 - This Love (Official Music Video)",
            platform=Platform.YOUTUBE,
            track_id="UkRFTTRwWUpwN3hKU2VqaFhZOVRZZ1V6UHcuWFBwVGdDaG81WkE="
        )

    def test_get_track_info_from_link_non_youtube_link(self):
        self.assertFalse(self.service.get_track_info_from_link(link=SPOTIFY_LINK_WEB))

    def test_get_track_info_from_link_web(self):
        ti = self.service.get_track_info_from_link(link=YOUTUBE_LINK_WEB)

        self.assertTrue(isinstance(ti, TrackInfo))
        # cheating here a little bit because I know that the default behavior of this fake client
        # and wht it will return
        self.assertEqual(ti.name, "Maroon 5 - This Love (Official Music Video)")


    def test_get_track_info_from_link_mobile(self):
        ti = self.service.get_track_info_from_link(link=YOUTUBE_LINK_MOBILE)

        self.assertTrue(isinstance(ti, TrackInfo))
        # cheating here a little bit because I know that the default behavior of this fake client
        # and wht it will return
        self.assertEqual(ti.name, "Maroon 5 - This Love (Official Music Video)")

    def test_track_info_no_results(self):
        service = YoutubeService(
            credentials={'ok': True},
            client=FakeYoutubeClient(expected_responses={'videos_list': {'items': []}})
        )

        self.assertFalse(service.get_track_info_from_link(link=YOUTUBE_LINK_MOBILE))

    def test_get_track_ids_in_playlist(self):
        track_ids = self.service.get_track_ids_in_playlist(playlist=self.playlist)

        #some cheating here because I know what the ids will be from the json fake
        expected_track_ids = {self.track_info.track_id, }

        self.assertEqual(track_ids, expected_track_ids)

    def test_is_track_in_playlist_and_it_is(self):
        self.assertTrue(self.service.is_track_in_playlist(
            track_info=self.track_info,
            playlist=self.playlist
        ))
    
    def test_is_track_in_playlist_and_it_is_not(self):
        self.assertFalse(self.service.is_track_in_playlist(
            track_info=TrackInfo(name='nah', platform=Platform.YOUTUBE, track_id='nah'),
            playlist=self.playlist
        ))    


    def test_add_track_to_playlist_fails_error(self):
        def raise_exception():
            raise Exception('nope')

        fake_client = FakeYoutubeClient(
            expected_responses={
                'playlistItems_list': {'items': []},
                'playlistItem_insert': raise_exception
            }
        )

        service = YoutubeService(
            credentials={'ok': True},
            client=fake_client
        )

        self.assertEqual(
            service.add_track_to_playlist(track_info=self.track_info, playlist=self.playlist),
            (False, 'nope')
        )
    
    def test_add_track_to_playlist_fails_duplicate(self):
        self.assertEqual(
            self.service.add_track_to_playlist(track_info=self.track_info, playlist=self.playlist),
            (False, DUPLICATE_TRACK)
        )

    def test_add_track_to_playlist_succeeds(self):
        fake_client = FakeYoutubeClient(expected_responses={'playlistItems_list': {'items': []}})
        service = YoutubeService(
            credentials={'ok': True},
            client=fake_client
        )

        self.assertEqual(
            service.add_track_to_playlist(track_info=self.track_info, playlist=self.playlist),
            (True, None)
        )

        self.assertEqual(
            fake_client.insert_calls[0],
            {
                'kind': 'youtube#playlistItem',
                'snippet': {
                    'playlistId': self.playlist.platform_id,
                    'resourceId': {
                        'kind': 'youtube#video',
                        'videoId': self.track_info.track_id,
                    }
                }
            }
        )

    def test_fuzzy_search_for_track_no_results_over_fuzz_limit(self):
        spotify_ti = TrackInfo(
            name="Sure",
            artists="Why not",
            platform=Platform.SPOTIFY
        )

        target = spotify_ti.track_name_for_comparison()
        # set up some bad results
        results = copy.deepcopy(YOTUBE_SEARCH_LIST_RESPONSE)
        items = results['items']
        bad_items = []
        for item in items:
            current_name = item['snippet']['title']
            while fuzz.token_set_ratio(spotify_ti.track_name_for_comparison(), current_name) >= 85:
                current_name += "a"
            
            item['snippet']['title'] = current_name
            bad_items.append(item)
        
        results['items'] = bad_items
        fake_client = FakeYoutubeClient(expected_responses={
            "search": results
        })
        service = YoutubeService(credentials={'ok': True}, client=fake_client)

        self.assertIsNone(service.fuzzy_search_for_track(track_info=spotify_ti))

    def test_fuzzy_search_for_track_good_results(self):
        spotify_ti = TrackInfo(
            name="Sure",
            artists="Why not",
            platform=Platform.SPOTIFY
        )

        target = spotify_ti.track_name_for_comparison()
        # set up some bad results
        results = copy.deepcopy(YOTUBE_SEARCH_LIST_RESPONSE)
        items = results['items']
        bad_items = []
        for item in items[:-1]:
            # make sure all but one are bad
            current_name = spotify_ti.track_name_for_comparison()
            while fuzz.token_set_ratio(spotify_ti.track_name_for_comparison(), current_name) >= 85:
                current_name += "a"
            
            item['snippet']['title'] = current_name
            bad_items.append(item)
        
        # make one item that's good
        good_item = items[-1]
        # don't make it perfect, for some reason
        pretty_good_title = spotify_ti.track_name_for_comparison() + 'a'
        good_item['snippet']['title'] = pretty_good_title
        bad_items.append(good_item)
        
        results['items'] = bad_items
        fake_client = FakeYoutubeClient(expected_responses={
            "search": results
        })
        service = YoutubeService(credentials={'ok': True}, client=fake_client)
        match = service.fuzzy_search_for_track(track_info=spotify_ti)

        self.assertIsInstance(match, TrackInfo)
        self.assertTrue(match.name, pretty_good_title)

    def test_create_playlist(self):
        pass

class ServiceTestCase(DatabaseTestBase):
    def test_get_track_info_from_link(self):
        pass

    def test_get_track_ids_in_playlist(self):
        pass

    def test_is_track_in_playlist(self):
        pass

    def test_add_track_to_playlist(self):
        pass

    def test_fuzzy_search_for_track(self):
        pass

    def test_create_playlist(self):
        pass