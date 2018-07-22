from enum import Enum


class InvalidEnumException(Exception):
    pass


class SlackUrl(Enum):
    CHANNEL_HISTORY = "https://slack.com/api/channels.history"
    POST_MESSAGE = "https://slack.com/api/chat.postMessage"
    CHAT_UPDATE = "https://slack.com/api/chat.update"
    OUATH_ACCESS = 'https://slack.com/api/oauth.access'


class MusicService(Enum):
    YOUTUBE = 'Youtube'
    SPOTIFY = 'Spotify'
    GMUSIC = 'Gmusic'

    @classmethod
    def from_string(cls, string):
        if string.lower()[0] == 'y':
            return cls.YOUTUBE
        elif string.lower()[0] == 's':
            return cls.SPOTIFY
        elif string.lower()[0] == 'g':
            return cls.GMUSIC
        else:
            raise InvalidEnumException

    @classmethod
    def from_link(cls, link):
        if 'yout' in link:
            return cls.YOUTUBE
        elif 'spotify' in link:
            return cls.SPOTIFY
        elif 'play.google.com/music' in link:
            return cls.GMUSIC
        else:
            return None