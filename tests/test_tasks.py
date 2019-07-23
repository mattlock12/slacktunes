import json
import unittest
from unittest.mock import call, patch

from tests.base import DatabaseTestBase
from tests.fakes import FakeSpotifyClient, FakeYoutubeClient, FakeServiceFactory
from src.constants import Platform
from src.message_formatters import SlackMessageFormatter
from src.models import Credential, Playlist, User
from src.new_services import ServiceFactory, TrackInfo, YoutubeService
from src.tasks import add_link_to_playlists
from settings import SLACKTUNES_USER_ID


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


class TestAddTrackToPlaylistsTestCase(DatabaseTestBase):
    def setUp(self):
        super(TestAddTrackToPlaylistsTestCase, self).setUp()
        self.user = User(
            name=SLACKTUNES_USER_ID,
            slack_id='abc123'
        )
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
        self.message_formatter_mock = self.message_formatter_patcher.start()

    def tearDown(self):
        super(TestAddTrackToPlaylistsTestCase, self).tearDown()

        self.message_formatter_patcher.stop()

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
            yt_playlists.append(ytpl)

        for s in range(num_spot):
            spl = Playlist(
                platform=Platform.SPOTIFY,
                platform_id="abc%s" % s,
                name="Youtube Playlist %s" % s,
                channel_id=channel_id,
                user_id=user.id
            )
            spot_playlists.append(spl)
        
        return yt_playlists, spot_playlists


    @patch('src.tasks.get_track_info_from_link', return_value=None)
    def test_no_native_track_info(self, *args):
        channel_id = 'abc123'
        link_id = "123123"
        link = "https:youtube.co/watch?v=%s" % link_id
        
        add_link_to_playlists(
            link=link,
            playlists=[],
            channel=channel_id,
            formatter_class=SlackMessageFormatter
        )

        self.message_formatter_mock.called_once_with(payload={
            'channel': channel_id,
            'text': 'Unable to find info for link %s' % link
        })

    @patch('src.tasks.get_track_info_from_link', return_value=YT_TRACK_INFO)
    def test_adds_same_service_platforms(self, *args):
        channel_id = 'abc123'
        link_id = "123123"
        link = "https:youtube.co/watch?v=%s" % link_id
        yt_playlists, _ = self._make_playlists(num_yt=2, channel_id=channel_id)

        expected_successes = [(pl, None) for pl in yt_playlists]
        with patch('src.tasks.add_track_to_playlists', return_value=(expected_successes, [])) as add_mock:
            add_link_to_playlists(
                link=link,
                playlists=yt_playlists,
                channel=channel_id,
                formatter_class=SlackMessageFormatter
            )

        self.assertEqual(add_mock.call_count, 1)
        add_mock.assert_called_with(playlists=yt_playlists, track_info=YT_TRACK_INFO)
        # cheating because I know the output
        self.message_formatter_mock.assert_called_once_with(payload={
            'channel': 'abc123',
            'blocks': [
                {
                    'type': 'section',
                    'text': {
                        'type': 'mrkdwn',
                        'text': '*<https://www.youtube.com/watch?v=abc123|Maroon 5 - This Love>*\nWas added to playlists:\n*Youtube Playlist 0* (Youtube)\n*Youtube Playlist 1* (Youtube)'
                    },
                    'accessory': {
                        'type': 'image',
                        'image_url': None,
                        'alt_text': 'Maroon 5 - This Love'
                    }
                }
            ]
        })

    @patch('src.tasks.get_track_info_from_link', return_value=YT_TRACK_INFO)
    def test_adds_same_service_with_failures(self, *args):
        channel_id = 'abc123'
        link_id = "123123"
        link = "https:youtube.co/watch?v=%s" % link_id
        yt_playlists, _ = self._make_playlists(num_yt=2, channel_id=channel_id)

        expected_successes = [(yt_playlists[0], None)]
        expected_failures = [(yt_playlists[1], None)]
        with patch('src.tasks.add_track_to_playlists', return_value=(expected_successes, expected_failures)) as add_mock:
            add_link_to_playlists(
                link=link,
                playlists=yt_playlists,
                channel=channel_id,
                formatter_class=SlackMessageFormatter
            )

        self.assertEqual(add_mock.call_count, 1)
        add_mock.assert_called_with(playlists=yt_playlists, track_info=YT_TRACK_INFO)
        # cheating because I know the output
        self.message_formatter_mock.assert_called_once_with(payload={
            'channel': 'abc123',
            'blocks': [
                {
                    'type': 'section',
                    'text': {
                        'type': 'mrkdwn',
                        'text': '*<https://www.youtube.com/watch?v=abc123|Maroon 5 - This Love>*\nWas added to playlists:\n*Youtube Playlist 0* (Youtube)\nFailed to add to playlists:\n*Youtube Playlist 1* (Youtube) None'
                    },
                    'accessory': {
                        'type': 'image',
                        'image_url': None,
                        'alt_text': 'Maroon 5 - This Love'
                    }
                }
            ]
        })

    @patch('src.tasks.get_track_info_from_link', return_value=YT_TRACK_INFO)
    @patch('src.tasks.fuzzy_search_from_track_info', return_value=None)
    def test_cross_platform_no_best_match(self, *args):
        channel_id = 'abc123'
        link_id = "123123"
        link = "https:youtube.co/watch?v=%s" % link_id
        _, spot_playlists = self._make_playlists(num_yt=0, num_spot=2, channel_id=channel_id)

        expected_successes = []
        expected_failures = [(sp, "No matching track found") for sp in spot_playlists]
        with patch('src.tasks.add_track_to_playlists', return_value=(expected_successes, expected_failures)) as add_mock:
            add_link_to_playlists(
                link=link,
                playlists=spot_playlists,
                channel=channel_id,
                formatter_class=SlackMessageFormatter
            )

        self.assertEqual(add_mock.call_count, 0)
        # cheating because I know the output
        self.message_formatter_mock.assert_called_once_with(payload={
            'channel': 'abc123',
            'blocks': [
                {
                    'type': 'section',
                    'text': {
                        'type': 'mrkdwn',
                        'text': 'Unable to find Youtube track for Maroon 5 - This Love\n\nWill schedule another search in 1 week'
                        }
                    },
                    {
                        'type': 'context',
                        'elements': [
                            {
                                'type': 'mrkdwn',
                                'text': 'Attempted match from Youtube link *<https://www.youtube.com/watch?v=abc123|Maroon 5 - This Love>*'
                            }
                        ]
                    }
            ]
        })
    
    @patch('src.tasks.get_track_info_from_link', return_value=YT_TRACK_INFO)
    @patch('src.tasks.fuzzy_search_from_track_info', return_value=SP_TRACK_INFO)
    def test_cross_platform_with_match(self, *args):
        channel_id = 'abc123'
        link_id = "123123"
        link = "https:youtube.co/watch?v=%s" % link_id
        yt_playlists, spot_playlists = self._make_playlists(num_yt=2, num_spot=2, channel_id=channel_id)
        all_playlists = yt_playlists + spot_playlists

        expected_yt_successes = [(yt_playlists[0], None)]
        expected_yt_failures = [(yt_playlists[1], "Bad")]
        expected_sp_successes = [(spot_playlists[0], None)]
        expected_sp_failures = [(spot_playlists[1], "Bad")]

        with patch('src.tasks.add_track_to_playlists') as add_mock:
            add_mock.side_effect = [(expected_yt_successes, expected_yt_failures), (expected_sp_successes, expected_sp_failures)]
            add_link_to_playlists(
                link=link,
                playlists=all_playlists,
                channel=channel_id,
                formatter_class=SlackMessageFormatter
            )

            self.assertEqual(add_mock.call_count, 2)
            expected_calls = [
                call(playlists=yt_playlists, track_info=YT_TRACK_INFO),
                call(playlists=spot_playlists, track_info=SP_TRACK_INFO)
            ]
            add_mock.assert_has_calls(expected_calls)

        self.message_formatter_mock.assert_called_with(payload={
            'channel':
            'abc123',
            'blocks': [
                {
                    'type': 'section',
                    'text': {
                        'type': 'mrkdwn',
                        'text': '*<https://www.youtube.com/watch?v=abc123|Maroon 5 - This Love>*\nWas added to playlists:\n*Youtube Playlist 0* (Youtube)\nFailed to add to playlists:\n*Youtube Playlist 1* (Youtube) Bad'
                    }, 
                    'accessory': {
                        'type': 'image',
                        'image_url': None,
                        'alt_text': 'Maroon 5 - This Love'
                    }
                },
                {
                    'type': 'divider'
                },
                {
                    'type': 'section',
                    'text': {
                        'type': 'mrkdwn',
                        'text': '*<https://open.spotify.com/track/def456|This Love - Maroon, 5>*\nWas added to playlists:\n*Youtube Playlist 0* (Spotify)\nFailed to add to playlists:\n*Youtube Playlist 1* (Spotify) Bad'
                    },
                    'accessory': {
                        'type': 'image',
                        'image_url': None,
                        'alt_text': 'This Love - Maroon, 5'
                    }
                },
                {
                    'type': 'context',
                    'elements': [
                        {
                            'type': 'mrkdwn',
                            'text': 'Attempted match from Youtube link *<https://www.youtube.com/watch?v=abc123|Maroon 5 - This Love>*'
                        }
                    ]
                }
            ]
        })