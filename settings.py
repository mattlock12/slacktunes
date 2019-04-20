import os

"""
Requires a dev.env file to set these for dev
"""
BASE_URI = os.environ.get('NGROK_URL', None)

SLACK_CLIENT_ID = os.environ.get('SLACK_CLIENT_ID', None)
SLACK_CLIENT_SECRET = os.environ.get('SLACK_CLIENT_SECRET', None)
SLACK_OAUTH_TOKEN = os.environ.get('SLACK_OAUTH_TOKEN', None)
SLACK_VERIFICATION_TOKEN = os.environ.get('SLACK_VERIFICATION_TOKEN', None)
SERVICE_SLACK_ID = ''

SLACKTUNES_USER_ID = ''

YOUTUBE_CLIENT_ID = os.environ.get('YOUTUBE_CLIENT_ID', None)
YOUTUBE_CLIENT_SECRET = os.environ.get('YOUTUBE_CLIENT_SECRET', None)

SPOTIFY_CLIENT_ID = os.environ.get('SPOTIFY_CLIENT_ID', None)
SPOTIFY_CLIENT_SECRET = os.environ.get('SPOTIFY_CLIENT_SECRET', None)

MYSQL_DB_FORMAT = 'postgresql+psycopg2://{username}:{password}@{server}:{port}/{db}'
MYSQL_USERNAME = 'slacktuner'
MYSQL_PASSWORD = 'slacktuner'
MYSQL_SERVER = 'db'
MYSQL_PORT = '5432'
MYSQL_DBNAME = 'slacktunes_dev'

DB_URI = MYSQL_DB_FORMAT.format(
    username=MYSQL_USERNAME,
    password=MYSQL_PASSWORD,
    server=MYSQL_SERVER,
    port=MYSQL_PORT,
    db=MYSQL_DBNAME
)

try:
    from local_settings import *
except ImportError:
    pass

YOUTUBE_REDIRECT_URI = '%s/youtubeoauth2callback' % BASE_URI
SPOTIFY_REDIRECT_URI = "%s/spotifyoauth2callback" % BASE_URI
