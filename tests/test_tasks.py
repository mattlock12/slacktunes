import json
import unittest

from .base import DatabaseTestBase
from src.constants import Platform
from src.models import Credential, User
from src.new_services import TrackInfo
from src.tasks import add_link_to_playlists
from settings import SERVICE_SLACK_USER_NAME



LINKS_TO_TRACKS = {
    "https://youtube.com/watch?v=abc123": TrackInfo(
        name="Maroon 5 This Love",
        platform=Platform.YOUTUBE,
        track_id="abc123"
    ),
    "https://open.spotify.com/def345": TrackInfo(
        name="Mr Brightside",
        artists="The Killers",
        track_id="def345",
        platform=Platform.SPOTIFY
    )
}


class FakeServiceFactory(object):
    YOUTUBE_FAIL = False
    SPOTIFY_FAIL = False
    
    @classmethod
    def from_enum(cls, enum):
        if enum is Platform.YOUTUBE:
            if cls.YOUTUBE_FAIL:
                return FakeServiceFails
            
            return FakeServiceSucceeds
        elif enum is Platform.SPOTIFY:
            if cls.SPOTIFY_FAIL:
                return FakeServiceFails
            
            return FakeServiceSucceeds
        else:
            return None


class FakeServiceFactoryYTFail(FakeServiceFactory):
    YOUTUBE_FAIL = True


class FakeServiceFactorySFail(FakeServiceFactory):
    SPOTIFY_FAIL = True


class FakeServiceSucceeds(object):
    FAIL = False
    ADD_TRACK_ERROR = "FAIL ADD TRACK"
    
    def __init__(self, credentials):
        self.credentials = credentials

    def get_track_info_from_link(self, link):        
        return LINKS_TO_TRACKS.get(link)

    def add_track_to_playlist(self, track_info, playlist):
        if self.FAIL:
            return False, self.ADD_TRACK_ERROR
        
        playlist.tracks.append(track_info)
        
        return True, None


class FakeServiceFails(FakeServiceSucceeds):
    FAIL = True


class FakePlaylist(object):
    def __init__(self, name, platform, tracks=[]):
        self.name = name
        self.platform = platform
        self.tracks = tracks


class TestAddLinkToPlaylist(DatabaseTestBase):
    def setUp(self):
        super(TestAddLinkToPlaylist, self).setUp()

        slacktunes_user = User(
            name=SERVICE_SLACK_USER_NAME,
            slack_id=1
        )
        slacktunes_user.save()
        # create some fake creds for each platform
        Credential(
            user_id=slacktunes_user.id,
            platform=Platform.YOUTUBE,
            credentials=json.dumps({'ok': true})
        )
        Credential(
            user_id=slacktunes_user.id,
            platform=Platform.SPOTIFY,
            credentials=json.dumps({'ok': true})
        )

        self.yt_playlists = [
            Play(
                name="Fake YT 1",
                platform=Platform.YOUTUBE
            ),
            FakePlaylist(
                name="Fake YT 2",
                platform=Platform.YOUTUBE
            )
        ]
        
        self.s_playlists = [
            FakePlaylist(
                name="Fake S 1",
                platform=Platform.SPOTIFY
            ),
            FakePlaylist(
                name="Fake S 2",
                platform=Platform.SPOTIFY
            )
        ]

        self.all_playlists = self.yt_playlists + self.s_playlists


    def test_no_native_track_info(self):
        bad_link = "https://youtube.com/watch?v=notagoodid"

        add_link_to_playlists(
            link=bad_link,
            playlists=self.all_playlists,
            channel='whatev'
        )

        self.assertEqual(
            [],
            [track for pl in self.all_playlists for track in pl.tracks]
        )
    
    def test_native_playlists(self):
        pass

    def test_native_track_info_only_cp_playlists_best_match(self):
        pass

    def test_both_playlists_no_best_match(self):
        pass
    
    def test_both_playlists_best_match(self):
        pass