import copy
import unittest

from spotipy.client import SpotifyException
from fuzzywuzzy import fuzz

from src.constants import BAD_WORDS, DUPLICATE_TRACK, Platform
from src.models import Playlist
from src.music_services import (
    ServiceFactory,
    SpotifyService,
    TrackInfo,
    YoutubeService,
    YOUTUBE_TOKEN_SET_THRESHHOLD,
)
from tests.fakes import FakeSpotifyClient, FakeYoutubeClient
from tests.json_fakes import (
    YOUTUBE_PLAYLIST_INSERT_RESPONSE,
    YOTUBE_SEARCH_LIST_RESPONSE,
    YOUTUBE_VIDEOS_LIST_SINGLE_RESPONSE,
    SPOTIFY_TRACK_RESP,
    SPOTIFY_PLAYLIST_TRACKS_RESP,
)

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
        track_info_no_artist = TrackInfo(
            platform=Platform.YOUTUBE,
            name='ok',
            track_id='123'
        )
        self.assertEqual(track_info_no_artist.artists_display_name(), '')

        track_info_list_of_artists = TrackInfo(
            platform=Platform.YOUTUBE,
            name='ok',
            track_id='123',
            artists=['foo', 'bar']
        )
        self.assertEqual(
            track_info_list_of_artists.artists_display_name(),
            "foo, bar"
        )

        track_info_artist_string = TrackInfo(
            platform=Platform.YOUTUBE,
            name='ok',
            track_id='123',
            artists='foo bar'
        )
        self.assertEqual(
            track_info_artist_string.artists_display_name(),
            'foo bar'
        )

    def artists_for_search(self):
        self.assertEqual(
            TrackInfo(
                platform=Platform.YOUTUBE,
                name='ok',
                track_id='123',
                artists=['foo', 'bar']
            ).artists_for_search(),
            ""
        )

        self.assertEqual(
            TrackInfo(
                platform=Platform.SPOTIFY,
                name='ok',
                track_id='123',
                artists=['foo', 'bar']
            ).artists_for_search(),
            "foo bar"
        )

    def test_track_name_for_comparison(self):
        # should sanitize title and append artists without commas
        track_name = "This Love [%s] (%s)" % (BAD_WORDS[0], BAD_WORDS[1])
        artists = ["Maroon 5", "Kabir"]

        self.assertEqual(
            TrackInfo(
                platform=Platform.SPOTIFY,
                name=track_name,
                track_id='123',
                artists=artists
            ).track_name_for_comparison(),
            "This Love Maroon 5 Kabir"
        )

    def test_track_name_for_display(self):
        track_name = "This Love [%s] (%s)" % (BAD_WORDS[0], BAD_WORDS[1])
        artists = ["Maroon 5", "Kabir"]

        self.assertEqual(
            TrackInfo(
                platform=Platform.SPOTIFY,
                name=track_name,
                track_id='123',
                artists=artists
            ).track_name_for_display(),
            "%s - %s" % (track_name, ", ".join(artists))
        )

    def test_description(self):
        self.assertEqual(
            TrackInfo(
                platform=Platform.SPOTIFY,
                name="ok",
                track_id='123',
                artists=["ok"]
            ).description(),
            ""
        )

        self.assertEqual(
            TrackInfo(
                platform=Platform.YOUTUBE,
                name="ok",
                track_id='123',
                raw_json=YOUTUBE_VIDEOS_LIST_SINGLE_RESPONSE['items'][0]['snippet']
            ).description(),
            "It's fuckin' Maroon 5!"
        )

    def test_channel_title(self):
        self.assertEqual(
            TrackInfo(
                platform=Platform.YOUTUBE,
                name="ok",
                track_id='123',
                raw_json=YOUTUBE_VIDEOS_LIST_SINGLE_RESPONSE['items'][0]['snippet']
            ).channel_title(),
            "Maroon5VEVO"
        )

    def test_track_open_url_youtube(self):
        track_id = '123'
        self.assertEqual(
            TrackInfo(
                platform=Platform.YOUTUBE,
                name="ok",
                track_id=track_id
            ).track_open_url(),
            "https://www.youtube.com/watch?v=%s" % track_id
        )
        self.assertEqual(
            TrackInfo(
                platform=Platform.SPOTIFY,
                name="ok",
                track_id=track_id
            ).track_open_url(),
            "https://open.spotify.com/track/%s" % track_id
        )

    def test_track_image_url(self):
        self.assertEqual(
            TrackInfo(
                platform=Platform.YOUTUBE,
                name="ok",
                track_id='123',
                raw_json=YOUTUBE_VIDEOS_LIST_SINGLE_RESPONSE['items'][0]['snippet']
            ).track_image_url(),
            "https://i.ytimg.com/vi/XPpTgCho5ZA/default.jpg"
        )

        self.assertEqual(
            TrackInfo(
                platform=Platform.SPOTIFY,
                name="ok",
                track_id='123',
                raw_json=SPOTIFY_TRACK_RESP
            ).track_image_url(),
            "https://i.scdn.co/image/6ecbb6e0db1a5093bc58169b87beb19d2947ebdd"
        )

    def test_sanitized_track_name(self):
        base_str = "Maroon  5 (YES) [123]"
        for word in BAD_WORDS:
            base_str += " %s" % word

            self.assertEqual(
                TrackInfo(
                    platform=Platform.YOUTUBE,
                    track_id='123',
                    name=base_str
                ).sanitized_track_name().strip(),
                'Maroon 5'.strip()
            )


class ServiceFactoryTestCase(unittest.TestCase):
    def test_from_string(self):
        for yt_string in ['y', 'Y']:
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


class YoutubeServiceTestCase(unittest.TestCase):
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
            track_id="XPpTgCho5ZA"
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
            fake_client.playlist_item_insert_calls[0],
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

    def test_best_match_no_results_over_fuzz_limit(self):
        # set up some bad results
        target = "Sure Why not"
        results = copy.deepcopy(YOTUBE_SEARCH_LIST_RESPONSE)
        items = results['items']
        bad_items = []
        for item in items:
            current_name = item['snippet']['title']
            while fuzz.token_set_ratio(target, current_name) >= YOUTUBE_TOKEN_SET_THRESHHOLD:
                current_name += "a"

            item['snippet']['title'] = current_name
            bad_items.append(item)

        fake_client = FakeYoutubeClient()
        service = YoutubeService(credentials={'ok': True}, client=fake_client)

        self.assertIsNone(service.best_match(target_string=target, search_results=bad_items))

    def test_best_match_good_results(self):
        # set up some bad results
        target = "Sure Why not"
        results = copy.deepcopy(YOTUBE_SEARCH_LIST_RESPONSE)
        items = results['items']
        bad_items = []
        for item in items[:-1]:
            # make sure all but one are bad
            current_name = target
            while fuzz.token_set_ratio(target, current_name) >= YOUTUBE_TOKEN_SET_THRESHHOLD:
                current_name += "a"

            item['snippet']['title'] = current_name
            bad_items.append(item)

        # make one item that's good
        good_item = items[-1]
        # don't make it perfect, for some reason
        pretty_good_title = target + 'a'
        good_item['snippet']['title'] = pretty_good_title
        bad_items.append(good_item)

        fake_client = FakeYoutubeClient()
        service = YoutubeService(credentials={'ok': True}, client=fake_client)
        match = service.best_match(target_string=target, search_results=bad_items)

        self.assertIsInstance(match, TrackInfo)
        self.assertTrue(match.name, pretty_good_title)

    def test_list_playlists(self):
        self.assertEqual(
            [p['snippet']['title'] for p in self.service.list_playlists()],
            ['Playlist1', 'Playlist2']
        )

    def test_create_playlist_no_channel(self):
        fake_client = FakeYoutubeClient(expected_responses={
            'channels_list': {'items': []}
        })
        service = YoutubeService(credentials=True, client=fake_client)

        self.assertEqual(
            service.create_playlist(playlist_name='foobar'),
            (False, 'No channels')
        )

    def test_create_playlist_dupe_playlist(self):
        fake_client = FakeYoutubeClient(expected_responses={
            'playlists_list':
            {
                'items': [
                    {
                        'snippet': {'title': self.playlist.name}
                    }
                ]
            }
        })
        service = YoutubeService(credentials=True, client=fake_client)

        self.assertTrue(service.create_playlist(playlist_name=self.playlist.name))
        self.assertEqual(fake_client.playlist_item_insert_calls, [])

    def test_create_playlist(self):
        title = 'sure thing'
        res = self.service.create_playlist(playlist_name=title)

        expected_res = copy.deepcopy(YOUTUBE_PLAYLIST_INSERT_RESPONSE)
        expected_res['snippet']['title'] = title
        expected_res['snippet']['localized']['title'] = title

        self.assertEqual((True, expected_res), res)
        self.assertTrue(self.service.client.playlist_insert_calls, [title])

class SpotifyServiceTestCase(unittest.TestCase):
    def setUp(self):
        super(SpotifyServiceTestCase, self).setUp()

        self.fake_client = FakeSpotifyClient()
        self.service = SpotifyService(credentials={'ok': True}, client=self.fake_client)

        self.playlist = Playlist(
            name="Spot",
            platform=Platform.SPOTIFY,
            platform_id='abc123',
            user_id=1,
            channel_id='123'
        )

        self.track_info = TrackInfo(
            name="This Love",
            artists=[a['name'] for a in SPOTIFY_TRACK_RESP['artists']],
            platform=Platform.SPOTIFY,
            track_id="aaa"
        )

    def test_get_track_info_from_link_desktop(self):
        info = self.service.get_track_info_from_link(link=SPOTIFY_LINK_DESKTOP)

        self.assertIsInstance(info, TrackInfo)
        self.assertEqual(info.name, self.track_info.name)

    def test_get_track_info_from_link_web(self):
        info = self.service.get_track_info_from_link(link=SPOTIFY_LINK_WEB)

        self.assertIsInstance(info, TrackInfo)
        self.assertEqual(info.name, self.track_info.name)

    def test_get_track_ids_in_playlist(self):
        expected_ids = {t['track']['id'] for t in SPOTIFY_PLAYLIST_TRACKS_RESP['items']}

        self.assertEqual(
            self.service.get_track_ids_in_playlist(playlist=self.playlist),
            expected_ids
        )

    def test_is_track_in_playlist_is_in_playlist(self):
        # cheat because I know this id is in the json fakes
        self.track_info.track_id = '6ECp64rv50XVz93WvxXMGF'
        self.assertTrue(self.service.is_track_in_playlist(
            track_info=self.track_info, playlist=self.playlist))

    def test_is_track_in_playlist_is_not_in_playlist(self):
        self.track_info.track_id = 'nope'
        self.assertFalse(self.service.is_track_in_playlist(
            track_info=self.track_info, playlist=self.playlist))


    def test_list_playlists_no_user_info(self):
        fake_client = FakeSpotifyClient(expected_responses={
            'me': None
        })
        service = SpotifyService(credentials=True, client=fake_client)

        self.assertEqual([], service.list_playlists())

    def test_list_playlists(self):
        # don't want it returning .next() results
        self.service.client.nexted = True
        # cheating because I know what this returns form the fake client
        self.assertEqual(
            [{'name': 'Playlist1'}, {'name': 'Playlist2'}],
            self.service.list_playlists()
        )


    def test_add_track_to_playlist_exception(self):
        def raiser():
            raise Exception('nope')

        def s_raiser():
            raise SpotifyException(code=1, msg='snope', http_status=500)

        fake_client = FakeSpotifyClient(expected_responses={
            'user_playlist_add_tracks': raiser
        })
        exc_service = SpotifyService(credentials={'ok': True}, client=fake_client)

        fake_client_spotify_error = FakeSpotifyClient(expected_responses={
            'user_playlist_add_tracks': s_raiser
        })
        sexc_service = SpotifyService(credentials={'ok': True}, client=fake_client_spotify_error)

        self.assertEqual(
            (False, 'nope'),
            exc_service.add_track_to_playlist(
                playlist=self.playlist,
                track_info=self.track_info
            )
        )
        self.assertEqual(
            (False, 'snope'),
            sexc_service.add_track_to_playlist(
                playlist=self.playlist,
                track_info=self.track_info
            )
        )

    def test_add_track_to_playlist_bad_resp(self):
        fake_client = FakeSpotifyClient(expected_responses={
            'user_playlist_add_tracks': {'nope': False}
        })
        service = SpotifyService(credentials={'ok': True}, client=fake_client)

        self.assertEqual(
            (False, 'Unable to add %s to %s' % (self.track_info.name, self.playlist.name)),
            service.add_track_to_playlist(track_info=self.track_info, playlist=self.playlist)
        )

    def test_add_track_to_playlist(self):
        self.track_info.track_id = 'foobar'

        self.assertEqual(
            (True, None),
            self.service.add_track_to_playlist(track_info=self.track_info, playlist=self.playlist)
        )
        self.assertEqual(
            self.fake_client.add_track_calls,
            [self.track_info.track_id]
        )

    def test_create_playlist_no_user_info(self):
        fake_client = FakeSpotifyClient(expected_responses={
            'me': None
        })
        service = SpotifyService(credentials=True, client=fake_client)

        self.assertEqual(
            (False, "Could not find info for this user"),
            service.create_playlist(playlist_name='ok')
        )

    def test_create_playlist_dupe_playlist(self):
        dupe_name = 'Playlist1'

        self.assertEqual(
            (True, {'name': 'Playlist1'}),
            self.service.create_playlist(playlist_name=dupe_name)
        )

    def test_create_playlist_create_exception(self):
        def raiser():
            raise Exception("Nope")

        fake_client = FakeSpotifyClient(expected_responses={
            'user_playlist_create': raiser
        })
        # don't want results from .next()
        fake_client.nexted = True
        service = SpotifyService(credentials=True, client=fake_client)

        self.assertEqual(
            (False, "Failed to create playlist"),
            service.create_playlist(playlist_name='whatever')
        )

    def test_create_playlist(self):
        pl_name = 'ok'

        # don't want results from .next()
        self.service.client.nexted = True
        self.assertEqual(
            (True, {'name': pl_name}),
            self.service.create_playlist(playlist_name=pl_name)
        )


class SpotifyClientFuzzyMatchTestCase(unittest.TestCase):
    def test_fuzzy_search_for_track_bad_results(self):
        pass

    # ====== token set stage =====
    def test_fuzzy_search_for_track_token_set_no_contenders(self):
        pass

    def test_fuzzy_search_for_track_token_set_one_contender(self):
        pass

    # ===== token sort stage =====
    def test_fuzzy_search_for_track_token_sort_one_contender(self):
        pass
