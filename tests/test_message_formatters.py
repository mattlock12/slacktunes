import unittest

from src.constants import Platform
from src.models import Playlist
from src.message_formatters import SlackMessageFormatter
from src.music_services import TrackInfo


class TestSlackMessageFormatter(unittest.TestCase):
    def setUp(self):
        self.yt_playlist_one = Playlist(
            name="Test Playlist 1",
            platform=Platform.YOUTUBE,
            platform_id='abc123',
            channel_id='abc123',
            user_id=1
        )
        self.yt_playlist_two = Playlist(
            name="Test Playlist 2",
            platform=Platform.YOUTUBE,
            platform_id='def456',
            channel_id='abc123',
            user_id=2
        )

        self.yt_track_info = TrackInfo(
            name="test",
            track_id='456',
            platform=Platform.YOUTUBE
        )

    def test_total_failure_message_returns_text_with_link(self):
        link = 'https://slacktunes.io'
        self.assertEqual(
            {
                "text": "Unable to find info for link %s" % link,
            },
            SlackMessageFormatter.total_failure_message(link=link)
        )

    def test_format_results_block_no_successes_or_failures(self):
        formatter = SlackMessageFormatter()

        self.assertEqual(
            {},
            formatter.format_results_block(track_info=None, successes=None, failures=None)
        )

    def test_format_results_block_only_successes(self):
        formatter = SlackMessageFormatter()

        expected_success_str = """*<{track_url}|{track_name}>*
Was added to playlists:
*{pl_name}* ({pl_platform})
*{other_pl_name}* ({other_pl_platform})""".format(
            track_url=self.yt_track_info.track_open_url(),
            track_name=self.yt_track_info.get_track_name(),
            pl_name=self.yt_playlist_one.name,
            pl_platform=self.yt_playlist_one.platform.name.title(),
            other_pl_name=self.yt_playlist_two.name,
            other_pl_platform=self.yt_playlist_two.platform.name.title(),
        )
        expected = {
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": expected_success_str
            },
            "accessory": {
                "type": "image",
                "image_url": self.yt_track_info.track_image_url(),
                "alt_text": self.yt_track_info.get_track_name()
            }
        }

        actual = formatter.format_results_block(
            track_info=self.yt_track_info,
            successes=[(self.yt_playlist_one, None), (self.yt_playlist_two, None)],
            failures=[]
        )

        self.assertEqual(expected, actual)

    def test_format_results_block_only_failures(self):
        formatter = SlackMessageFormatter()

        expected_success_str = "*<{track_url}|{track_name}>*".format(
            track_url=self.yt_track_info.track_open_url(),
            track_name=self.yt_track_info.get_track_name()
        )
        fake_reason = "capnhoops is a tugboat captain"
        fake_reason_2 = "sarink is musty af"
        expected_failure_str = """
Failed to add to playlists:
*{pl_name}* ({pl_platform}) {reason}
*{other_pl_name}* ({other_pl_platform}) {other_reason}""".format(
            pl_name=self.yt_playlist_one.name,
            pl_platform=self.yt_playlist_one.platform.name.title(),
            reason=fake_reason,
            other_pl_name=self.yt_playlist_two.name,
            other_pl_platform=self.yt_playlist_two.platform.name.title(),
            other_reason=fake_reason_2
        )
        expected = {
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": expected_success_str + expected_failure_str
            },
            "accessory": {
                "type": "image",
                "image_url": self.yt_track_info.track_image_url(),
                "alt_text": self.yt_track_info.get_track_name()
            }
        }

        actual = formatter.format_results_block(
            track_info=self.yt_track_info,
            successes=[],
            failures=[(self.yt_playlist_one, fake_reason), (self.yt_playlist_two, fake_reason_2)]
        )

        self.assertEqual(expected, actual)
    
    def test_format_results_block_successes_and_failures(self):
        yt_playlist_three = Playlist(
            name="Youtube Playlist 3",
            platform=Platform.YOUTUBE,
            platform_id='asdfasdf',
            user_id=1,
            channel_id='abc123'
        )
        yt_playlist_four = Playlist(
            name="Youtube Playlist 3",
            platform=Platform.YOUTUBE,
            platform_id='asdfasdf',
            user_id=1,
            channel_id='abc123'
        )

        track_link = "*<%s|%s>*" % (self.yt_track_info.track_open_url(), self.yt_track_info.get_track_name())
        expected_success_str = """{track_link}
Was added to playlists:
*{pl_name}* ({pl_platform})
*{other_pl_name}* ({other_pl_platform})""".format(
            track_link=track_link,
            track_url=self.yt_track_info.track_open_url(),
            track_name=self.yt_track_info.get_track_name(),
            pl_name=self.yt_playlist_one.name,
            pl_platform=self.yt_playlist_one.platform.name.title(),
            other_pl_name=self.yt_playlist_two.name,
            other_pl_platform=self.yt_playlist_two.platform.name.title(),
        )

        fake_reason = "idk"
        fake_reason_2 = "idgaf"
        # NOTE: there is an intentional \n here
        expected_failure_str = """
Failed to add to playlists:
*{pl_name}* ({pl_platform}) {reason}
*{other_pl_name}* ({other_pl_platform}) {other_reason}""".format(
            pl_name=yt_playlist_three.name,
            pl_platform=yt_playlist_three.platform.name.title(),
            reason=fake_reason,
            other_pl_name=yt_playlist_four.name,
            other_pl_platform=yt_playlist_four.platform.name.title(),
            other_reason=fake_reason_2
        )

        expected = {
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": expected_success_str + expected_failure_str
            },
            "accessory": {
                "type": "image",
                "image_url": self.yt_track_info.track_image_url(),
                "alt_text": self.yt_track_info.get_track_name()
            }
        }

        formatter = SlackMessageFormatter()
        actual = formatter.format_results_block(
            track_info=self.yt_track_info,
            successes=[(self.yt_playlist_one, None), (self.yt_playlist_two, None)],
            failures=[(yt_playlist_three, fake_reason), (yt_playlist_four, fake_reason_2)]
        )

        self.assertEqual(expected, actual)

    def test_format_add_link_message_only_native_results(self):
        successes = [(self.yt_playlist_one, None),]
        failures = [(self.yt_playlist_two, None),]
        formatter = SlackMessageFormatter(
            native_track_info=self.yt_track_info,
            native_platform_successes=successes,
            native_platform_failures=failures
        )
        
        actual = formatter.format_add_link_message()
        expected = {
            "blocks": [
                formatter.format_results_block(track_info=self.yt_track_info, successes=successes, failures=failures)
            ]
        }

        self.assertEqual(len(actual['blocks']), 1)
        self.assertEqual(expected, actual)

    
    def test_format_add_link_message_only_cp_results(self):
        native_track_info = TrackInfo(
            name="SpotifyTrack",
            platform=Platform.SPOTIFY,
            artists="Noone",
            track_id="321"
        )

        successes = [(self.yt_playlist_one, None),]
        failures = [(self.yt_playlist_two, None),]
        formatter = SlackMessageFormatter(
            native_track_info=native_track_info,
            cross_platform_track_info=self.yt_track_info,
            cross_platform_successes=successes,
            cross_platform_failures=failures
        )
        actual = formatter.format_add_link_message()
        
        track_link = "*<%s|%s>*" % (native_track_info.track_open_url(), native_track_info.get_track_name())
        expected = {
            "blocks": [
                formatter.format_results_block(track_info=self.yt_track_info, successes=successes, failures=failures),
                {
                    "type": "context",
                    "elements": [
                        {
                            "type": "mrkdwn",
                            "text": "Attempted match from %s link %s" % (native_track_info.platform.name.title(), track_link)
                        }
                    ]
                }
            ]
        }

        self.assertEqual(len(actual['blocks']), 2)
        self.assertEqual(expected, actual)
    
    def test_format_add_link_message_both_results_no_cp_track_info(self):
        native_successes = [(self.yt_track_info, None)]
        native_failures = [(self.yt_track_info, "Bad")]

        cp_playlist_1 = Playlist(
            name="Test Playlist 1 Spotify",
            platform=Platform.SPOTIFY,
            platform_id='zzzzzzz',
            channel_id='abc123',
            user_id=2
        )

        track_link = "*<%s|%s>*" % (self.yt_track_info.track_open_url(), self.yt_track_info.get_track_name())

        formatter = SlackMessageFormatter(
            native_track_info=self.yt_track_info,
            native_platform_successes=native_successes,
            native_platform_failures=native_failures,
            cross_platform_failures=[(cp_playlist_1, "Bad")]
        )

        expected = {
            "blocks": [
                formatter.format_results_block(track_info=self.yt_track_info, successes=native_successes, failures=native_failures),
                {"type": "divider"},
                formatter.format_no_results_block(cross_platform_track_info=self.yt_track_info),
                {
                    "type": "context",
                    "elements": [
                        {
                            "type": "mrkdwn",
                            "text": "Attempted match from %s link %s" % (self.yt_track_info.platform.name.title(), track_link)
                        }
                    ]
                }
            ]
        }

        actual = formatter.format_add_link_message()

        self.assertEqual(expected, actual)

    def test_format_add_link_message_both_results_cp_track_info(self):
        native_successes = [(self.yt_track_info, None)]
        native_failures = [(self.yt_track_info, "Bad")]

        cp_track_info = TrackInfo(
            name="SpotifyTrack",
            platform=Platform.SPOTIFY,
            artists="Noone",
            track_id="321"
        )
        cp_playlist_1 = Playlist(
            name="Test Playlist 1 Spotify",
            platform=Platform.SPOTIFY,
            platform_id='zzzzzzz',
            channel_id='abc123',
            user_id=2
        )
        cp_playlist_2 = Playlist(
            name="Test Playlist 2 Spotify",
            platform=Platform.SPOTIFY,
            platform_id='xxxxxx',
            channel_id='abc123',
            user_id=2
        )

        cp_successes = [(cp_playlist_1, None), ]
        cp_failures = [(cp_playlist_2, "Bad"), ]

        track_link = "*<%s|%s>*" % (self.yt_track_info.track_open_url(), self.yt_track_info.get_track_name())

        formatter = SlackMessageFormatter(
            native_track_info=self.yt_track_info,
            native_platform_successes=native_successes,
            native_platform_failures=native_failures,
            cross_platform_track_info=cp_track_info,
            cross_platform_successes=cp_successes,
            cross_platform_failures=cp_failures
        )

        expected = {
            "blocks": [
                formatter.format_results_block(track_info=self.yt_track_info, successes=native_successes, failures=native_failures),
                {"type": "divider"},
                formatter.format_results_block(track_info=cp_track_info, successes=cp_successes, failures=cp_failures),
                {
                    "type": "context",
                    "elements": [
                        {
                            "type": "mrkdwn",
                            "text": "Attempted match from %s link %s" % (self.yt_track_info.platform.name.title(), track_link)
                        }
                    ]
                }
            ]
        }

        actual = formatter.format_add_link_message()

        self.assertEqual(expected, actual)
