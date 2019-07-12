import os

"""
Requires a dev.env file to set these for dev
"""
BASE_URI = os.environ.get('BASE_URI', None)

SLACK_CLIENT_ID = os.environ.get('SLACK_CLIENT_ID', None)
SLACK_CLIENT_SECRET = os.environ.get('SLACK_CLIENT_SECRET', None)
SLACK_OAUTH_TOKEN = os.environ.get('SLACK_OAUTH_TOKEN', None)
SLACK_VERIFICATION_TOKEN = os.environ.get('SLACK_VERIFICATION_TOKEN', None)
SERVICE_SLACK_ID = ''

SLACKTUNES_USER_ID = ''

YOUTUBE_CLIENT_ID = os.environ.get('YOUTUBE_CLIENT_ID', None)
YOUTUBE_CLIENT_SECRET = os.environ.get('YOUTUBE_CLIENT_SECRET', None)
YOUTUBE_REDIRECT_URI = '%s/youtubeoauth2callback' % BASE_URI

SPOTIFY_CLIENT_ID = os.environ.get('SPOTIFY_CLIENT_ID', None)
SPOTIFY_CLIENT_SECRET = os.environ.get('SPOTIFY_CLIENT_SECRET', None)
SPOTIFY_REDIRECT_URI = "%s/spotifyoauth2callback" % BASE_URI

PSQL_DB_FORMAT = 'postgresql+psycopg2://{username}:{password}@{server}:{port}/{db}'
PSQL_USERNAME = os.environ.get('PG_SLACKTTUNES_USER', 'slacktuner')
PSQL_PASSWORD = os.environ.get('PG_SLACKTUNES_PASSWORD', 'slacktuner')
PSQL_SERVER = os.environ.get('PG_SLACKTUENS_SERVER', 'db')
PSQL_PORT = os.environ.get('PG_SLACKTUNES_PORT', '5432')
PSQL_DBNAME = os.environ.get('PG_SLACKTUNES_DBNAME', 'slacktunes_dev')

DB_URI = PSQL_DB_FORMAT.format(
    username=PSQL_USERNAME,
    password=PSQL_PASSWORD,
    server=PSQL_SERVER,
    port=PSQL_PORT,
    db=PSQL_DBNAME
)
