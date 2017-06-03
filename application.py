import httplib2
import json
import logging
import os
import time
import uuid

import requests

from apiclient.discovery import build
from config import get_config
from flask import render_template, jsonify, redirect, request, url_for, Flask
from oauth2client import client

from constants import slack_chat_post_url, slack_history_url
from utils import get_youtube_links, strip_video_id

application = Flask(__name__)
application.secret_key = str(uuid.uuid4())

logger = logging.getLogger(__name__)
config = get_config()

CHANNEL_ID = config['CHANNEL_ID']
PLAYLIST_ID = config['PLAYLIST_ID']

SLACK_CLIENT_ID = config['SLACK_CLIENT_ID']
SLACK_CLIENT_SECRET = config['SLACK_CLIENT_SECRET']
SLACK_OAUTH_TOKEN = config['SLACK_OAUTH_TOKEN']
SLACK_VERIFICATION_TOKEN = config['SLACK_VERIFICATION_TOKEN']

YOUTUBE_CLIENT_ID = config['YOUTUBE_CLIENT_ID']
YOUTUBE_CLIENT_SECRET = config['YOUTUBE_CLIENT_SECRET']
BASE_URI = config['BASE_URI']
REDIRECT_URI = '%s/oauth2callback' % BASE_URI

SCOPE = 'https://www.googleapis.com/auth/youtube'
API_SERVICE_NAME = "youtube"
API_VERSION = "v3"
ALERT_UNAUTHED_INTERVAL = 3600  # 1x per hour

APP_CACHE = {}
youtube_service = False


def get_youtube_service():
    credentials = APP_CACHE.get('youtube_credentials', None)
    if not credentials:
        logger.error("No cached credentials found")
        post_update_to_chat(url=slack_chat_post_url,
                            payload={
                                'channel': CHANNEL_ID,
                                'text': 'No credentials. Re-auth at %s' % REDIRECT_URI
                         })
        return False

    http_auth = credentials.authorize(httplib2.Http())
    return build(API_SERVICE_NAME, API_VERSION, http=http_auth)


@application.route('/')
def index():
    return render_template("index.html", auth_uri=url_for('oauth2callback'))


# route used for slack oauth redirect
@application.route('/oauth/')
def oauth():
    code = request.args.get('code', None)
    payload = {
        'client_id': SLACK_CLIENT_ID,
        'client_secret': SLACK_CLIENT_SECRET,
        'code': code
    }

    r = requests.get(url='https://slack.com/api/oauth.access', params=payload)
    if r.status_code == 200:
        return redirect(url_for('index'))
    else:
        return r.text, 500


# route used for youtube oauth flow
@application.route('/oauth2callback')
def oauth2callback():
  flow = client.OAuth2WebServerFlow(client_id=YOUTUBE_CLIENT_ID,
                                    client_secret=YOUTUBE_CLIENT_SECRET,
                                    scope=SCOPE,
                                    redirect_uri=REDIRECT_URI)
  flow.params['access_type'] = 'offline'
  if 'code' not in request.args:
    auth_uri = flow.step1_get_authorize_url()
    return redirect(auth_uri)
  else:
    auth_code = request.args.get('code')
    credentials = flow.step2_exchange(auth_code)
    APP_CACHE['youtube_credentials'] = credentials
    APP_CACHE['has_posted_auth_error'] = 0
    logger.info("Successfully got credentials from youtube")

    global youtube_service
    youtube_service = get_youtube_service()
    return jsonify("Logged in")


@application.route('/init_playlist/', methods=['GET', 'POST'])
def init_playlist():
    if request.form.get('channel_name') == 'directmessage':
        return "Can't currently init playlist from private channel", 200

    return "Playlist already initialized. New initialization in V2", 200

    # channel = request.form['channel_id']
    # payload = {
    #     "token": os.environ['SLACK_OAUTH_TOKEN'],
    #     "channel": channel,
    #     "count": 1000
    # }
    #
    # channel_history = requests.post(url=slack_history_url, data=payload)
    # channel_history_jsonable = channel_history.json().get('messages')
    # youtube_links = get_youtube_links(channel_history=channel_history_jsonable)
    # youtube_video_ids = {strip_video_id(link) for link in youtube_links}
    #
    # if not getattr(application, 'youtube_credentials', None):
    #     return post_update_to_chat(url=slack_chat_post_url,
    #                                payload={"channel": channel, "text": "Auth token expired. Get @matt to visit %s%s to reauth" % (request.url_root[:-1], url_for('oauth2callback'))})
    # youtube = get_youtube_service()
    # if not youtube:
    #     return post_update_to_chat(url=slack_chat_post_url,
    #                                payload={"channel": channel, "text": "Could not get authenticated youtube service"})
    #
    # existing_playlist_items = youtube.playlistItems().list(part='snippet', playlistId=PLAYLIST_ID).execute()
    # existing_playlist_ids = {item['snippet']['resourceId']['videoId'] for item in existing_playlist_items['items']}
    #
    # ids_to_add = youtube_video_ids - existing_playlist_ids
    #
    # for id in ids_to_add:
    #     add_video_to_playlist(id, youtube=youtube)


def post_update_to_chat(url, payload):
    payload.update({"token": SLACK_OAUTH_TOKEN})
    res = requests.post(url=url, data=payload)

    return res.text, res.status_code


def add_video_to_playlist(video_id, playlist_id=PLAYLIST_ID, position=''):
    global youtube_service

    added_video_ids = APP_CACHE.get('added_youtube_video_ids', set())
    if not added_video_ids:
        added_video_ids = set()
        playlist_items_list_request = youtube_service.playlistItems().list(part='snippet', playlistId=PLAYLIST_ID, maxResults=50)
        while playlist_items_list_request:
            playlist_items_list_response = playlist_items_list_request.execute()
            for item in playlist_items_list_response['items']:
                added_video_ids.add(item['snippet']['resourceId']['videoId'])

            playlist_items_list_request = youtube_service.playlistItems().list_next(playlist_items_list_request, playlist_items_list_response)

    if video_id in added_video_ids:
        logger.info("Found posted video in already added ids. Not adding")
        return False

    added_video_ids.add(video_id)
    APP_CACHE['added_youtube_video_ids'] = added_video_ids

    resource_body = {
        'kind': 'youtube#playlistItem',
        'snippet': {
            'playlistId': playlist_id,
            'resourceId': {
                'kind': 'youtube#video',
                'videoId': video_id,
            }
        }
    }

    try:
        results = youtube_service.playlistItems().insert(
            body=resource_body,
            part='snippet'
        ).execute()
        return (True, results)
    except Exception as e:
        logger.exception(e)
        return (False, e)



# handles incoming event hooks
@application.route("/slack_events/", methods=['GET', 'POST'])
def slack_events():
    if request.data and json.loads(request.data.decode('utf-8')).get('challenge'):
        return json.loads(request.data.decode('utf-8')).get('challenge'), 200

    request_data_dict = json.loads(request.data.decode('utf-8'))
    event = request_data_dict.get('event')
    if not event:
        logger.error("Received event from slack with no event")
        return "No event", 400

    # verify token from slack in Basic Information
    if not request_data_dict.get('token') or request_data_dict.get('token') != SLACK_VERIFICATION_TOKEN:
        logger.error("Incorrect slack verification token")
        return "Incorrect token", 400

    if event.get('type') != 'link_shared':
        logger.info("Received event that was not link_shared")
        return "Ok", 200

    channel = event.get('channel')
    logger.info("%s action received in channel %s" % (event.get('type'), channel))

    if channel != CHANNEL_ID:
        return "Non werktune channel link share", 200

    links = event.get('links', None)
    if not links:
        logger.error("No links in event")
        return "No link", 400

    link = links[0]
    if 'youtube' not in link.get('domain'):
        logger.info("Yet another non-youtube link. You should get on that")
        return "Not a youtube link", 200

    video_id = strip_video_id(link['url'])

    global youtube_service
    if not youtube_service:
        logger.error("No authed service. Please authenticate")
        last_time_alerted = APP_CACHE.get('has_posted_auth_error', 0)
        now = int(time.time())
        if not last_time_alerted or now >= (last_time_alerted + ALERT_UNAUTHED_INTERVAL):
            APP_CACHE['has_posted_auth_error'] = now
            return post_update_to_chat(url=slack_chat_post_url,
                                       payload={
                                           'channel': CHANNEL_ID,
                                           'text': 'No auth creds! Get @matt to go to %s and reauth' % REDIRECT_URI}
                                       )
        return "Couldn't get authenticated youtube service", 200

    success, result = add_video_to_playlist(video_id=video_id)
    msg = "Added video to werktunes"
    if not success:
        msg = result

    return post_update_to_chat(url=slack_chat_post_url,
                               payload={
                                   "channel": channel,
                                   "text": msg
                               })

if __name__ == '__main__':
    application.run(host='0.0.0.0', port=8000)

