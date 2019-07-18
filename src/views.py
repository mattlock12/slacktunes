import json
from logging.handlers import RotatingFileHandler
from threading import Thread

import requests
from flask import render_template, jsonify, redirect, request, url_for
from functools import wraps


from settings import BASE_URI, SLACK_CLIENT_ID, SLACK_CLIENT_SECRET, SLACK_OAUTH_TOKEN, SLACK_VERIFICATION_TOKEN

from app import application
from .constants import InvalidEnumException, Platform, SlackUrl
from .models import Credential, Playlist, User
from .music_services import ServiceBase, TrackInfo
from .utils import get_links, post_update_to_chat, add_link_to_playlists_from_event, add_manual_track_to_playlists


# UTILITY DECORATOR
def verified_slack_request(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        request_data_dict = {}

        if request.data:
            request_data_dict = json.loads(request.data.decode('utf-8'))
        elif request.form:
            request_data_dict = request.form

        if request_data_dict.get('token', None) != SLACK_VERIFICATION_TOKEN:
            return "Not verified slack message", 400
        return f(*args, **kwargs)
    return decorated_function


# VIEWS
@application.route('/')
def index():
    return render_template("index.html")


@application.route('/oauthsuccess/<platform_abbrv>')
def oauthsuccess(platform_abbrv):
    platform = Platform.from_string(platform_abbrv)
    return jsonify("Successfully authed with %s!" % platform.name.title())


@application.route('/auth/s/<platform_str>/u/<userdata>')
def auth(platform_str, userdata):
    service = ServiceBase.from_string(platform_str)
    slack_user_id, slack_user_name = userdata.split(':')
    if not slack_user_id or not slack_user_name or not service:
        return "Couldn't auth: no slack userdata", 500

    auth_uri = service.get_auth_uri(state=userdata)
    return redirect(auth_uri)


# route used for slack oauth redirect
@application.route('/slackoauth/')
def slackoauth():
    code = request.args.get('code', None)
    payload = {
        'client_id': SLACK_CLIENT_ID,
        'client_secret': SLACK_CLIENT_SECRET,
        'code': code
    }

    r = requests.get(url=SlackUrl.OUATH_ACCESS.value, params=payload)
    if r.status_code == 200:
        return redirect(url_for('index'))
    else:
        return r.text, 500


def credential_exchange(platform_enum):
    service = ServiceBase.from_enum(platform_enum)
    code = request.args.get('code', None)
    
    if not code:
        return "No code in request args", 400

    if 'state' not in request.args:
        return "No state param in request args", 400

    state = request.args.get('state', ":")
    slack_user_id, slack_username = state.split(':')
    if not slack_user_id or not slack_username:
        return "No userdata to associate", 400

    credentials = service.exchange(code=code, state=state)
    application.logger.info("Successfully got credentials from %s" % platform_enum.name.title())

    user = User.query.filter_by(slack_id=slack_user_id).first()
    if not user:
        user = User(slack_id=slack_user_id, name=slack_username)
        user.save()

    creds = [creds for creds in user.credentials if creds.platform is platform_enum]
    if not creds:
        user_credentials = Credential(user_id=user.id, platform=platform_enum, credentials=credentials.to_json())
    else:
        user_credentials = creds[0]
        user_credentials.credentials = credentials.to_json()
    user_credentials.save()

    return jsonify("Succesfully authed with %s!" % platform_enum.name.title(), 200)


# route used for youtube oauth flow
@application.route('/youtubeoauth2callback')
def youtubeoauth2callback():
    return credential_exchange(platform_enum=Platform.YOUTUBE)


# route used for spotify redirect
@application.route('/spotifyoauth2callback')
def spotifyoauth2callback():
    return credential_exchange(platform_enum=Platform.SPOTIFY)


@application.route('/list_playlists/', methods=['POST'])
@verified_slack_request
def list_playlists():
    channel_id = request.form['channel_id']

    playlists = Playlist.query.filter_by(channel_id=channel_id).all()
    playlists_with_platform = ["*%s* (%s)" % (pl.name, pl.platform.name.title()) for pl in playlists]
    msg_body = "Found *%s* playlists in this channel: \n%s" % (len(playlists), "\n".join(playlists_with_platform))

    post_update_to_chat(payload={"channel": channel_id, "text": msg_body})

    return "", 200


@application.route('/create_playlist/', methods=['POST'])
@verified_slack_request
def create_playlist():
    if request.form.get('channel_name') == 'directmessage':
        return "Can't init playlist from private channel", 200

    channel_id = request.form['channel_id']
    channel_name = request.form['channel_name']
    slack_user_id = request.form['user_id']
    slack_user_name = request.form['user_name']
    command_text_args = request.form['text'].split()

    # defaults
    playlist_name = "%s_%s" % (channel_name, slack_user_name)
    platform_enum = Platform.YOUTUBE
    if command_text_args:
        args_len = len(command_text_args)
        if args_len > 0:
            playlist_name = command_text_args[0]
        if args_len > 1:
            try:
                platform_enum = Platform.from_string(command_text_args[1])
            except InvalidEnumException:
                pass

    user = User.query.filter_by(slack_id=slack_user_id).first()
    if not user:
        # prompt them to auth on the website
        state = "%s:%s" % (slack_user_id, slack_user_name)
        return "No verified auth for %s. Please go to %s%s and allow access" % \
               (slack_user_name, BASE_URI, url_for('auth', platform=platform_enum.name.lower(), userdata=state))

    credentials = user.credentials_for_platform(platform=platform_enum)
    if not credentials:
        # prompt them to auth on the website
        state = "%s:%s" % (slack_user_id, slack_user_name)
        return "No verified auth for %s. Please go to %s%s and allow access" % \
               (slack_user_name, BASE_URI, url_for('auth', platform_str=platform_enum.name.lower(), userdata=state))

    music_service = ServiceBase.from_enum(platform_enum)(credentials=credentials)

    playlist = Playlist.query.filter_by(
        user_id=user.id,
        name=playlist_name,
        platform=platform_enum,
        channel_id=channel_id
    ).first()
    if playlist:
        return "Found a playlist %s (%s) for %s in this channel already" % (
            playlist_name, platform_enum.name.title(), slack_user_name)

    success, playlist_snippet = music_service.create_playlist(playlist_name=playlist_name)
    if not success:
        return "Unable to create playlist", 200

    playlist = Playlist(
        name=playlist_name,
        channel_id=channel_id,
        platform=platform_enum,
        platform_id=playlist_snippet['id'],
        user_id=user.id
    )
    playlist.save()

    return "Created playlist %s for %s in this channel!" % (
        playlist_name, slack_user_name), 200


@application.route('/scrape_music/', methods=['POST'])
@verified_slack_request
def scrape_music():
    channel_id = request.form['channel_id']
    command_text_args = request.form['text'].split()

    playlists_in_channel = Playlist.query.filter_by(channel_id=channel_id).all()
    if not playlists_in_channel:
        return "No playlists in this channel. Use */create_playlist playlist_name platform* to create one", 200

    if not len(command_text_args):
        return "Please specify a playlist name in your command", 200

    playlist_name = command_text_args[0]
    playlists_match = [pl for pl in playlists_in_channel if pl.name == playlist_name]
    if not playlists_match:
        return "I couldn't find a playlist named %s in this channel..." % playlist_name, 200

    playlist = playlists_match[0]
    user = playlist.user
    if not user or not user.credentials:
        return "Somehow there is no user associated with this playlist... Can't auth with music service", 200

    music_service = ServiceBase.from_enum(playlist.platform)(credentials=user.credentials_for_platform(playlist.platform))

    # TODO: more robust error handling here
    if playlist.platform_id not in {pl['id'] for pl in music_service.list_playlists()}:
        return "Remote playlist doesn't match local playlist...", 200

    history_payload = {
        "token": SLACK_OAUTH_TOKEN,
        "channel": channel_id,
        "count": 1000
    }

    channel_history = requests.post(url=SlackUrl.CHANNEL_HISTORY.value, data=history_payload)
    channel_history_jsonable = channel_history.json().get('messages')

    links = get_links(channel_history=channel_history_jsonable)
    results = music_service.add_links_to_playlist(playlist, links)
    successes = set()
    failures = set()
    for s, m in results:
        if s:
            successes.add(m)
        else:
            failures.add(m)
    # TODO: make this better
    # TODO: async is the way
    failure_msg = "Failed to add %s video(s)" % len(failures)
    success_msg = "Added %s video(s) to %s\n%s" % (len(successes), playlist_name, failure_msg)

    return success_msg, 200


@application.route("/delete_playlist/", methods=['POST'])
@verified_slack_request
def delete_playlist():
    channel_id = request.form['channel_id']
    channel_name = request.form['channel_name']
    slack_user_id = request.form['user_id']
    command_text_args = request.form['text'].split()

    if not command_text_args or len(command_text_args) < 1:
        return "Specify the name and platform of the playlist to delete", 200

    playlist_name = command_text_args[0]
    user = User.query.filter_by(slack_id=slack_user_id).first()
    if not user:
        return "No record of you, %s. Are you sure you have a playlist in this channel?", 200

    playlists = Playlist.query.filter_by(user_id=user.id, channel_id=channel_id)
    if not playlists:
        return "No playlists found in this channel that belong to you", 200

    playlist_to_delete = [pl for pl in playlists if pl.name == playlist_name]

    if len(command_text_args) > 1:
        platform_name = command_text_args[1]
        platform_enum = Platform.from_string(platform_name)
        playlist_to_delete = [pl for pl in playlist_to_delete if pl.platform is platform_enum]

    if not playlist_to_delete:
        existing_in_channel = "\n".join("%s (%s)" % (p.name, p.platform.name.title()) for p in playlists)
        return "Couldn't find a playlist named %s... I see these: \n%s" % (playlist_name, existing_in_channel), 200
    playlist_to_delete = playlist_to_delete[0]

    platform = playlist_to_delete.platform
    playlist_to_delete.delete()

    return "Deleted slacktunes record of *%s* in channel *%s* \n" \
           " Keep in mind, this won't delete the %s version, it'll only stop slacktunes" \
           "from posting links to it" % (playlist_name, channel_name, platform.name.title()), 200


@application.route("/add_track/", methods=['POST'])
@verified_slack_request
def add_track():
    """
    /add_track track_name | artist | playlist(optional) | platform(optional)
    """
    if request.form.get('channel_name') == 'directmessage':
        return "Can't add tracks in private channel", 200

    channel_id = request.form['channel_id']
    command_text_args = request.form['text'].split('|')

    if not command_text_args or len(command_text_args) < 2 or len(command_text_args) > 4:
        return "Usage: /add_track <track_name> | <artist> | <playlist_name [optional> | <platform [optional>", 200

    track_name = command_text_args.pop(0).strip()
    artist = command_text_args.pop(0).strip()
    playlist_name = None
    platform_str = None

    if command_text_args:
        playlist_name = command_text_args.pop(0).strip()

    if command_text_args:
        platform_str = command_text_args.pop(0).strip()

    # start thread to do this because slack requires a fast response and checking for dupes takes time
    t = Thread(
        target=add_manual_track_to_playlists,
        kwargs={
            'track_info': TrackInfo(name=track_name, artists=artist),
            'channel_id': channel_id,
            'playlist_name': playlist_name,
            'platform_str': platform_str
        })
    t.start()

    return '', 200


# handles incoming event hooks
@application.route("/slack_events/", methods=['POST'])
@verified_slack_request
def slack_events():
    application.logger.info("Received event")
    if not request.data:
        application.logger.error("No request data sent to /slack_events")
        return 400

    request_data_dict = json.loads(request.data.decode('utf-8'))
    if request_data_dict.get('challenge'):
        return request_data_dict.get('challenge'), 200

    event = request_data_dict.get('event')
    if not event:
        application.logger.error("Received event from slack with no event")
        return "No event", 400

    if event.get('type') != 'link_shared':
        application.logger.info("Received event that was not link_shared")
        return "Ok", 200

    # start thread to do this because slack requires a fast response and checking for dupes takes time
    t = Thread(
        target=add_link_to_playlists_from_event,
        args=(event, ))
    t.start()

    return "Ok", 200
