import os


BASE_URI = 'https://slacktunes.me'
try:
    SLACK_CLIENT_ID = os.environ['SLACK_CLIENT_ID']
    SLACK_CLIENT_SECRET = os.environ['SLACK_CLIENT_SECRET']
    SLACK_OAUTH_TOKEN = os.environ['SLACK_OAUTH_TOKEN']
    SLACK_VERIFICATION_TOKEN = os.environ['SLACK_VERIFICATION_TOKEN']

    YOUTUBE_CLIENT_ID = os.environ['YOUTUBE_CLIENT_ID']
    YOUTUBE_CLIENT_SECRET = os.environ['YOUTUBE_CLIENT_SECRET']

    MYSQL_DB_FORMAT = 'mysql+pymysql://{username}:{password}@{server}:{port}/{db}'
    MYSQL_USERNAME = os.environ['RDS_USER']
    MYSQL_PASSWORD = os.environ['RDS_PASSWORD']
    MYSQL_SERVER = os.environ['RDS_ENDPOINT']
    MYSQL_PORT = os.environ['RDS_PORT']
    MYSQL_DBNAME = os.environ['RDS_DBNAME']

    DB_URI = MYSQL_DB_FORMAT.format(
        username=MYSQL_USERNAME,
        password=MYSQL_PASSWORD,
        server=MYSQL_SERVER,
        port=MYSQL_PORT,
        db=MYSQL_DBNAME
    )

except KeyError:
    pass

try:
    from local_settings import *
except ImportError:
    pass

try:
    YOUTUBE_CLIENT_ID
except NameError as e:
    raise NameError("######## LOOKS LIKE YOU FORGOT TO UPDATE LOCAL SETTINGS! #################")

YOUTUBE_REDIRECT_URI = '%s/youtubeoauth2callback' % BASE_URI
