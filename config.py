import json
import os

PROD = 'PROD'


class DevConfig(object):
    def _get_config(self):
        with open('credentials.json', 'r') as creds:
            return json.loads(creds.read())

    def get_config(self):
        cfg = self._get_config()

        for k, v in cfg.items():
            if not v:
                raise Exception("Missing value in config %s" % k)

        return cfg


class ProdConfig(DevConfig):
    def _get_config(self):
        return {
            'SLACK_CLIENT_ID': os.environ['SLACK_CLIENT_ID'],
            'SLACK_CLIENT_SECRET': os.environ['SLACK_CLIENT_SECRET'],
            'SLACK_OAUTH_TOKEN': os.environ['SLACK_OAUTH_TOKEN'],
            'SLACK_VERIFICATION_TOKEN': os.environ['SLACK_VERIFICATION_TOKEN'],
            'PLAYLIST_ID': os.environ['PLAYLIST_ID'],
            'YOUTUBE_CLIENT_ID': os.environ['YOUTUBE_CLIENT_ID'],
            'YOUTUBE_CLIENT_SECRET': os.environ['YOUTUBE_CLIENT_SECRET'],
            'BASE_URI': 'https://slacktunes.me',
            'CHANNEL_ID': '',  # TODO: change me
        }


def get_config():
    try:
        if os.environ.get('ENV') == PROD:
            return ProdConfig().get_config()
    except KeyError:
        pass

    return DevConfig().get_config()