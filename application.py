import httplib2
import json
import os
import uuid

import requests

from apiclient.discovery import build
from flask import render_template, redirect, request, url_for, Flask
from oauth2client import client
from werkzeug.contrib.cache import SimpleCache

from constants import slack_chat_post_url, slack_history_url
from utils import get_youtube_links, strip_video_id

app = Flask(__name__)
app.secret_key = str(uuid.uuid4())
cache = SimpleCache()

PLAYLIST_ID = os.environ['PLAYLIST_ID']
YOUTUBE_CLIENT_ID = os.environ['YOUTUBE_CLIENT_ID']
YOUTUBE_CLIENT_SECRET = os.environ['YOUTUBE_CLIENT_SECRET']
REDIRECT_URI = 'https://slacktunes.me/oauth2callback/'
SCOPE = 'https://www.googleapis.com/auth/youtube https://www.googleapis.com/auth/youtubepartner'
API_SERVICE_NAME = "youtube"
API_VERSION = "v3"


def get_youtube_credentials():
    return cache.get('youtube_credentials')


def get_youtube_service():
    credentials = get_youtube_credentials()
    if not credentials:
        return False

    http_auth = credentials.authorize(httplib2.Http())
    return build(API_SERVICE_NAME, API_VERSION, http=http_auth)


@app.route('/')
def index():
    return render_template("index.html", auth_uri=url_for('oauth2callback'))


# route used for slack oauth redirect
@app.route('/oauth/')
def oauth():
    code = request.args.get('code', None)
    payload = {'client_id': os.environ['SLACK_CLIENT_ID'], 'client_secret': os.environ['SLACK_CLIENT_SECRET'], 'code': code}
    r = requests.get(url='https://slack.com/api/oauth.access', params=payload)
    if r.status_code == 200:
        return redirect(url_for('index'))
    else:
        return r.text, 500


# route used for youtube oauth flow
@app.route('/oauth2callback')
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
    cache.set('youtube_credentials', credentials)
    return redirect(url_for('index'))


@app.route('/init_playlist/', methods=['GET', 'POST'])
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
    # if not cache.get('youtube_credentials'):
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
    payload.update({"token": os.environ['SLACK_OAUTH_TOKEN']})
    res = requests.post(url=url, data=payload)

    return "Finished", res.status_code


def add_video_to_playlist(video_id, playlist_id=PLAYLIST_ID, youtube=None, position=''):
    if not youtube:
        youtube = get_youtube_service()

    added_video_ids = cache.get('video_ids')
    if not added_video_ids:
        added_video_ids = set()
        playlist_items_list_request = youtube.playlistItems().list(part='snippet', playlistId=PLAYLIST_ID, maxResults=50)
        while playlist_items_list_request:
            playlist_items_list_response = playlist_items_list_request.execute()
            for item in playlist_items_list_response['items']:
                added_video_ids.add(item['snippet']['resourceId']['videoId'])

            playlist_items_list_request = youtube.playlistItems().list_next(playlist_items_list_request, playlist_items_list_response)

        cache.set('video_ids', added_video_ids)

    if video_id in added_video_ids:
        return False

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
        results = youtube.playlistItems().insert(
            body=resource_body,
            part='snippet'
        ).execute()
    except Exception as e:
        results = False
    return results


# handles incoming event hooks
@app.route("/slack_events/", methods=['GET', 'POST'])
def slack_events():
    if request.data and json.loads(request.data.decode('utf-8')).get('challenge'):
        return json.loads(request.data.decode('utf-8')).get('challenge'), 200

    request_data_dict = json.loads(request.data.decode('utf-8'))
    event = request_data_dict.get('event')
    if not event:
        return "No event", 400

    # verify token from slack in Basic Information
    if request_data_dict.get('token') != os.environ['SLACK_VERIFICATION_TOKEN']:
        return "Incorrect token", 400

    if event.get('type') != 'link_shared':
        return "Ok", 200

    channel = event.get('channel')
    links = event.get('links', None)
    if not links:
        return "No link", 400

    link = links[0]
    if 'youtube' not in link.get('domain'):
        return "Not a youtube link", 200

    video_id = strip_video_id(link['url'])

    if not cache.get('youtube_credentials'):
        # return post_update_to_chat(url=slack_chat_post_url,
        #                            payload={"channel": channel, "text": "Auth token expired. Get @matt to visit %s%s to reauth" % (request.url_root[:-1], url_for('oauth2callback'))})
        return "ok", 200

    youtube = get_youtube_service()
    if not youtube:
        return "Couldn't get authenticated youtube service", 200

    result = add_video_to_playlist(video_id=video_id, youtube=youtube)
    if result:
        return post_update_to_chat(url=slack_chat_post_url,
                                   payload={
                                       "channel": channel,
                                       "text": "Added video to werktunes"
                                   })
    else:
        return "Ok", 200


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8000)