BASE_URI = 'https://slacktunes.me'

SLACK_CLIENT_ID = ''
SLACK_CLIENT_SECRET = ''
SLACK_OAUTH_TOKEN = ''
SLACK_VERIFICATION_TOKEN = ''

YOUTUBE_CLIENT_ID = ''
YOUTUBE_CLIENT_SECRET = ''

MYSQL_DB_FORMAT = 'mysql+pymysql://{username}:{password}@{server}:{port}/{db}'
MYSQL_USERNAME = ''
MYSQL_PASSWORD = ''
MYSQL_SERVER = ''
MYSQL_PORT = ''
MYSQL_DBNAME = ''

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
