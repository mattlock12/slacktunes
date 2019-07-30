import copy
import json
import unittest
from unittest.mock import call, patch

from tests.base import DatabaseTestBase
from src.constants import Platform
from src.message_formatters import SlackMessageFormatter
from src.models import Credential, Playlist, User
from src.music_services import ServiceFactory, TrackInfo, YoutubeService
from src.tasks import add_link_to_playlists, search_and_add_to_playlists


YT_TRACK_INFO = TrackInfo(
    name="Maroon 5 - This Love",
    platform=Platform.YOUTUBE,
    track_id='abc123'
)

SP_TRACK_INFO = TrackInfo(
    name="This Love",
    artists="Maroon 5",
    track_id="def456",
    platform=Platform.SPOTIFY
)


class TaskTestBase(DatabaseTestBase):
    def setUp(self):
        super(TaskTestBase, self).setUp()
        self.user = User(
            name='tester',
            slack_id='abc123'
        )
        self.user.is_service_user = True
        self.user.save()

        self.yt_creds = Credential (
            platform=Platform.YOUTUBE,
            credentials=json.dumps({'access_token': True}),
            user_id=self.user.id
        )
        self.yt_creds.save()

        self.s_creds = Credential (
            platform=Platform.SPOTIFY,
            credentials=json.dumps({'access_token': True}),
            user_id=self.user.id
        )
        self.s_creds.save()

        self.message_formatter_patcher = patch.object(SlackMessageFormatter, 'post_message', return_value=True)
        self.add_track_results_patcher = patch.object(SlackMessageFormatter, 'format_add_track_results_message', return_value={})
        self.message_formatter_mock = self.message_formatter_patcher.start()
        self.add_track_results_patcher = self.add_track_results_patcher.start()

    def tearDown(self):
        super(TaskTestBase, self).tearDown()

        self.message_formatter_patcher.stop()
        self.add_track_results_patcher.stop()

    def _make_playlists(self, channel_id, num_yt=0, num_spot=0, user=None):
        if not user:
            user = self.user
    
        yt_playlists = []
        spot_playlists = []
        
        for i in range(num_yt):
            ytpl = Playlist(
                platform=Platform.YOUTUBE,
                platform_id="abc%s" % i,
                name="Youtube Playlist %s" % i,
                channel_id=channel_id,
                user_id=user.id
            )
            ytpl.save()
            yt_playlists.append(ytpl)

        for s in range(num_spot):
            spl = Playlist(
                platform=Platform.SPOTIFY,
                platform_id="abc%s" % s,
                name="Youtube Playlist %s" % s,
                channel_id=channel_id,
                user_id=user.id
            )
            spl.save()
            spot_playlists.append(spl)
        
        return yt_playlists, spot_playlists



class TestAddTrackToPlaylistsTestCase(TaskTestBase):
    @patch('src.tasks.get_track_info_from_link', return_value=None)
    def test_no_native_track_info(self, *args):
        channel_id = 'abc123'
        link_id = "123123"
        link = "https:youtube.co/watch?v=%s" % link_id
        
        add_link_to_playlists(
            link=link,
            channel=channel_id
        )

        self.message_formatter_mock.called_once_with(payload={
            'channel': channel_id,
            'text': 'Unable to find info for link %s' % link
        })

    @patch('src.tasks.get_track_info_from_link', return_value=YT_TRACK_INFO)
    def test_no_native_playlists(self, track_info_mock):
        channel = '123'
        link = 'https://www.youtube.com/watch?v=123'
        _, spotify_playlists = self._make_playlists(
            channel_id=channel,
            num_yt=0,
            num_spot=2
        )
        yt_track_json = copy.deepcopy(YT_TRACK_INFO.__dict__)
        yt_track_json['platform'] = YT_TRACK_INFO.platform.name
        with patch('src.tasks.search_and_add_to_playlists.delay') as search_mock:
            with patch('src.tasks.add_track_to_playlists', return_value=([1], [2])) as add_track_mock:
                add_link_to_playlists(
                    link=link,
                    channel=channel
                )

                search_mock.assert_called_once_with(
                    channel=channel,
                    platform=Platform.SPOTIFY.name,
                    origin=yt_track_json
                )

                self.assertEqual(add_track_mock.call_count, 0)


    @patch('src.tasks.get_track_info_from_link', return_value=YT_TRACK_INFO)
    def test_native_playlists(self, track_info_mock):
        channel = '123'
        link = "https://www.youtube.com/watch?v=123"
        yt_playlists, spotify_playlists = self._make_playlists(
            channel_id=channel,
            num_yt=2,
            num_spot=2
        )
        yt_track_json = copy.deepcopy(YT_TRACK_INFO.__dict__)
        yt_track_json['platform'] = YT_TRACK_INFO.platform.name
        with patch('src.tasks.search_and_add_to_playlists.delay') as search_mock:
            with patch('src.tasks.add_track_to_playlists', return_value=([1], [2])) as add_track_mock:
                add_link_to_playlists(
                    link=link,
                    channel=channel
                )

                search_mock.assert_called_once_with(
                    channel=channel,
                    platform=Platform.SPOTIFY.name,
                    origin=yt_track_json
                )

                add_track_mock.assert_called_with(
                    playlists=yt_playlists,
                    track_info=YT_TRACK_INFO
                )
                self.add_track_results_patcher.assert_called_with(
                    successes=[1],
                    failures=[2],
                    track_info=YT_TRACK_INFO,
                    origin=link
                )


class SearchAndAddToPlaylistsTestCase(TaskTestBase):
    def setUp(self):
        super(SearchAndAddToPlaylistsTestCase, self).setUp()

        self.fuzzy_search_from_track_info_mock = patch('src.tasks.fuzzy_search_from_track_info').start()
        self.fuzzy_search_from_string_mock = patch('src.tasks.fuzzy_search_from_string').start()
        self.add_track_to_playlists_mock = patch('src.tasks.add_track_to_playlists').start()

        self.format_failed_search_results_message_mock = patch.object(SlackMessageFormatter, 'format_failed_search_results_message').start()
        self.format_add_track_results_message_mock = patch.object(SlackMessageFormatter, 'format_add_track_results_message').start()
        self.post_message_mock = patch.object(SlackMessageFormatter, 'post_message').start()

    def tearDown(self):
        super(SearchAndAddToPlaylistsTestCase, self).tearDown()

        self.fuzzy_search_from_track_info_mock.stop()
        self.fuzzy_search_from_string_mock.stop()
        self.add_track_to_playlists_mock.stop()
        self.format_failed_search_results_message_mock.stop()
        self.format_add_track_results_message_mock.stop()
        self.post_message_mock.stop()

    def test_no_playlists(self):
        channel = '123'
        self._make_playlists(num_yt=2, num_spot=0, channel_id='123')

        yt_track_json = copy.deepcopy(YT_TRACK_INFO.__dict__)
        yt_track_json['platform'] = YT_TRACK_INFO.platform.name


        search_and_add_to_playlists(origin=yt_track_json, platform=Platform.SPOTIFY.name, channel=channel)

        self.assertEqual(self.fuzzy_search_from_track_info_mock.call_count, 0)
        self.assertEqual(self.fuzzy_search_from_string_mock.call_count, 0)
        self.assertEqual(self.add_track_to_playlists_mock.call_count, 0)
        self.assertEqual(self.format_failed_search_results_message_mock.call_count, 0)
        self.assertEqual(self.format_add_track_results_message_mock.call_count, 0)
        self.assertEqual(self.post_message_mock.call_count, 0)


    def test_search_from_string_no_best_match(self):
        channel = '123'
        origin = {
            'track_name': "This Love",
            'artist': "Maroon 5"
        }
        self._make_playlists(num_yt=0, num_spot=2, channel_id=channel)

        self.fuzzy_search_from_string_mock.return_value = None
        self.format_failed_search_results_message_mock.return_value = {'ok': 'ok'}
        
        search_and_add_to_playlists(
            origin=origin,
            platform=Platform.SPOTIFY.name,
            channel=channel
        )

        self.fuzzy_search_from_string_mock.assert_called_once_with(
            artist=origin['artist'],
            track_name=origin['track_name'],
            platform=Platform.SPOTIFY
        )
        
        self.format_failed_search_results_message_mock.assert_called_once_with(
            origin=origin,
            target_platform=Platform.SPOTIFY
        )

        self.post_message_mock.assert_called_once_with(
            payload={
                'ok': 'ok',
                'channel': channel
            }
        )

        self.assertEqual(self.fuzzy_search_from_track_info_mock.call_count, 0)
        self.assertEqual(self.add_track_to_playlists_mock.call_count, 0)
        self.assertEqual(self.format_add_track_results_message_mock.call_count, 0)

    def test_search_from_jsonified_track_info_no_match(self):
        channel = '123'
        self._make_playlists(num_yt=0, num_spot=2, channel_id=channel)

        yt_track_json = copy.deepcopy(YT_TRACK_INFO.__dict__)
        yt_track_json['platform'] = YT_TRACK_INFO.platform.name

        self.fuzzy_search_from_track_info_mock.return_value = None
        self.format_failed_search_results_message_mock.return_value = {'ok': 'ok'}
        
        search_and_add_to_playlists(
            origin=yt_track_json,
            platform=Platform.SPOTIFY.name,
            channel=channel
        )

        # can't assert called_with here because it creates a TrackInfo object in the method
        self.fuzzy_search_from_track_info_mock.assert_called_once()
        self.format_failed_search_results_message_mock.assert_called_once()

        self.post_message_mock.assert_called_once_with(
            payload={
                'ok': 'ok',
                'channel': channel
            }
        )

        self.assertEqual(self.fuzzy_search_from_string_mock.call_count, 0)
        self.assertEqual(self.add_track_to_playlists_mock.call_count, 0)
        self.assertEqual(self.format_add_track_results_message_mock.call_count, 0)
    

    def test_best_match(self):
        channel = '123'
        origin = {
            'track_name': "This Love",
            'artist': "Maroon 5"
        }

        _, spls = self._make_playlists(num_yt=0, num_spot=2, channel_id=channel)
        self.fuzzy_search_from_string_mock.return_value = SP_TRACK_INFO
        self.add_track_to_playlists_mock.return_value = ([1], [2])
        self.format_add_track_results_message_mock.return_value = {'ok': 'ok'}
        
        search_and_add_to_playlists(
            origin=origin,
            platform=Platform.SPOTIFY.name,
            channel=channel
        )

        self.fuzzy_search_from_string_mock.assert_called_once_with(
            artist=origin['artist'],
            track_name=origin['track_name'],
            platform=Platform.SPOTIFY
        )
        self.add_track_to_playlists_mock.asset_called_once_with(
            track_info=SP_TRACK_INFO,
            playlists=spls
        )
        self.format_add_track_results_message_mock.assert_called_once_with(
            origin=origin,
            track_info=SP_TRACK_INFO,
            successes=[1],
            failures=[2]
        )

        self.post_message_mock.assert_called_once_with(
            payload={
                'ok': 'ok',
                'channel': channel
            }
        )

        self.assertEqual(self.fuzzy_search_from_track_info_mock.call_count, 0)
        self.assertEqual(self.format_failed_search_results_message_mock.call_count, 0)
