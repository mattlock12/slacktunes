from enum import Enum


DUPLICATE_TRACK = "Duplicate"

class InvalidEnumException(Exception):
    pass


class SlackUrl(Enum):
    CHANNEL_HISTORY = "https://slack.com/api/channels.history"
    POST_MESSAGE = "https://slack.com/api/chat.postMessage"
    CHAT_UPDATE = "https://slack.com/api/chat.update"
    OUATH_ACCESS = 'https://slack.com/api/oauth.access'


class Platform(Enum):
    YOUTUBE = 'Youtube'
    SPOTIFY = 'Spotify'

    @classmethod
    def from_string(cls, string):
        if string.lower()[0] == 'y':
            return cls.YOUTUBE
        elif string.lower()[0] == 's':
            return cls.SPOTIFY
        else:
            raise InvalidEnumException

    @classmethod
    def from_link(cls, link):
        if 'yout' in link:
            return cls.YOUTUBE
        elif 'spotify' in link:
            return cls.SPOTIFY
        else:
            return None


BAD_WORDS = [
    'EP',
    'Full',
    'Official',
    'Lyrics',
    'Lyric',
    'Video',
    'Album',
    'HD',
    'SD',
    'HQ',
    'by',
    'single',
    'version',
]
