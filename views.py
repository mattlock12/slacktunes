import base64
import json
import logging

import requests
from flask import current_app, render_template, jsonify, redirect, request, make_response, url_for
from functools import wraps

from application import application
from constants import InvalidEnumException, MusicService, SlackUrl
from models import Credential, Playlist, User
from music_services import ServiceBase
from settings import BASE_URI, SLACK_CLIENT_ID, SLACK_CLIENT_SECRET, SLACK_OAUTH_TOKEN, SLACK_VERIFICATION_TOKEN
from utils import get_links

logger = logging.getLogger(__name__)


# UTILITY DECORATOR
def verified_slack_request(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if request.data:
            request_data_dict = json.loads(request.data.decode('utf-8'))
        elif request.form:
            request_data_dict = request.form
        if request_data_dict['token'] != SLACK_VERIFICATION_TOKEN:
            return "Not verified slack message", 400
        return f(*args, **kwargs)
    return decorated_function


def post_update_to_chat(url, payload):
    payload.update({"token": SLACK_OAUTH_TOKEN})
    res = requests.post(url=url, data=payload)

    return res.text, res.status_code


# VIEWS
@application.route('/')
def index():
    return render_template("index.html")


@application.route('/oauthsuccess/<service_abbrv>')
def oauthsuccess(service_abbrv):
    service = MusicService.from_string(service_abbrv)
    return jsonify("Successfully authed with %s!" % service.name.title())


@application.route('/auth/s/<service>/u/<userdata>')
def auth(service, userdata):
    service = ServiceBase.from_string(service)
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


def credential_exchange(service_enum):
    service = ServiceBase.from_enum(service_enum)
    if 'code' not in request.args:
        return "No longer serviced by this view", 400
    elif 'state' not in request.args:
        return "No state param returned", 400
    else:
        state = request.args.get('state', ":")
        slack_user_id, slack_username = state.split(':')
        if not slack_user_id or not slack_username:
            return "No userdata to associate", 400
        code = request.args.get('code')
        credentials = service.exchange(code=code, state=state)
        logger.info("Successfully got credentials from %s" % service_enum.name.title())

        user = User.query.filter_by(slack_id=slack_user_id).first()
        if not user:
            user = User(slack_id=slack_user_id, name=slack_username)
            user.save()

        creds = [creds for creds in user.credentials if creds.service is service_enum]
        if not creds:
            user_credentials = Credential(user_id=user.id, service=service_enum, credentials=credentials.to_json())
        else:
            user_credentials = creds[0]
            user_credentials.credentials = credentials.to_json()
        user_credentials.save()

        return jsonify("Succesfully authed with %s!" % service_enum.name.title(), 200)


# route used for youtube oauth flow
@application.route('/youtubeoauth2callback')
def youtubeoauth2callback():
    service_enum = MusicService.YOUTUBE

    return credential_exchange(service_enum=service_enum)

# route used for spotify redirect
@application.route('/spotifyoauth2callback')
def spotifyoauth2callback():
    service_enum = MusicService.SPOTIFY

    return credential_exchange(service_enum=service_enum)


@application.route('/list_playlists/', methods=['POST'])
@verified_slack_request
def list_playlists():
    channel_id = request.form['channel_id']

    playlists = Playlist.query.filter_by(channel_id=channel_id).all()
    playlists_with_services = ["*%s* (%s)" % (pl.name, pl.service.name.title()) for pl in playlists]
    msg_body = "Found *%s* playlists in this channel: \n%s" % (len(playlists), "\n".join(playlists_with_services))

    post_update_to_chat(SlackUrl.POST_MESSAGE.value,
                        payload={
                            "channel": channel_id,
                            "text": msg_body
                        })

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
    music_service_enum = MusicService.from_string('y')
    if command_text_args:
        args_len = len(command_text_args)
        if args_len > 0:
            playlist_name = command_text_args[0]
        if args_len > 1:
            try:
                music_service_enum = MusicService.from_string(command_text_args[1])
            except InvalidEnumException:
                pass

    user = User.query.filter_by(slack_id=slack_user_id).first()
    if not user:
        # prompt them to auth on the website
        state = "%s:%s" % (slack_user_id, slack_user_name)
        return "No verified auth for %s. Please go to %s%s and allow access" % \
               (slack_user_name, BASE_URI, url_for('auth', service=music_service_enum.name.lower(), userdata=state))

    credentials = user.credentials_for_service(service=music_service_enum)
    if not credentials:
        # prompt them to auth on the website
        state = "%s:%s" % (slack_user_id, slack_user_name)
        return "No verified auth for %s. Please go to %s%s and allow access" % \
               (slack_user_name, BASE_URI, url_for('auth', service=music_service_enum.name.lower(), userdata=state))

    music_service = ServiceBase.from_string(music_service_enum.name)(credentials=credentials)

    success, playlist_snippet = music_service.create_playlist(playlist_name=playlist_name, user_id=user.id)
    if not success:
        return "Unable to create playlist", 200

    playlist = Playlist.query.filter_by(user_id=user.id, name=playlist_name, service=music_service_enum, channel_id=channel_id).first()
    if not playlist:
        playlist = Playlist(name=playlist_name,
                            channel_id=channel_id,
                            service=music_service_enum,
                            service_id=playlist_snippet['id'],
                            user_id=user.id)
        playlist.save()

    return "Created playlist %s for %s in this channel! Might I suggest /scrape_music next?" % (playlist_name, slack_user_name), 200


@application.route('/scrape_music/', methods=['POST'])
@verified_slack_request
def scrape_music():
    channel_id = request.form['channel_id']
    command_text_args = request.form['text'].split()

    playlists_in_channel = Playlist.query.filter_by(channel_id=channel_id).all()
    if not playlists_in_channel:
        return "No playlists in this channel. Use */create_playlist playlist_name service* to create one", 200

    if len(playlists_in_channel) > 1 and not len(command_text_args):
        return "Please specify a playlist name in your command", 200

    playlist_name = command_text_args[0]
    playlists_match = [pl for pl in playlists_in_channel if pl.name == playlist_name]
    if not playlists_match:
        return "I couldn't find a playlist named %s in this channel..." % playlist_name

    playlist = playlists_match[0]
    user = playlist.user
    if not user or not user.credentials:
        return "Somehow there is no user associated with this playlist...", 200

    music_service = ServiceBase.from_enum(playlist.service)(credentials=user.credentials_for_service(playlist.service))

    # TODO: more robust error handling here
    if playlist.service_id not in {pl['id'] for pl in music_service.list_playlists()}:
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
    successes = {m for s, m in results if s}
    failures = {m for f, m in results if not f}
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
        return "Specify the name and service of the playlist to delete", 200

    playlist_name = command_text_args[0]
    user = User.query.filter_by(slack_id=slack_user_id).first()
    if not user:
        return "No record of you, %s. Are you sure you have a playlist in this channel?", 200

    playlists = Playlist.query.filter_by(user_id=user.id, channel_id=channel_id)
    if not playlists:
        return "No playlists found in this channel that belong to you", 200

    playlist_to_delete = [pl for pl in playlists if pl.name == playlist_name]

    if len(command_text_args) > 1:
        service_name = command_text_args[1]
        service_enum = MusicService.from_string(service_name)
        playlist_to_delete = [pl for pl in playlist_to_delete if pl.service is service_enum]

    if not playlist_to_delete:
        return "Couldn't find a playlist named %s... I see these: %s" % \
               (playlist_name, ", ".join(map(lambda p: "%s (%s)" % (p.name, p.service.name.title()), playlists))), 200
    playlist_to_delete = playlist_to_delete[0]

    service = playlist_to_delete.service
    playlist_to_delete.delete()

    return "Deleted slacktunes record of *%s* in channel *%s* \n Keep in mind, this won't delete the %s version, it'll only stop slacktunes" \
           "from posting links to it" % (playlist_name, channel_name, service.name.title()), 200


# handles incoming event hooks
@application.route("/slack_events/", methods=['POST'])
@verified_slack_request
def slack_events():
    if request.data and json.loads(request.data.decode('utf-8')).get('challenge'):
        return json.loads(request.data.decode('utf-8')).get('challenge'), 200

    request_data_dict = json.loads(request.data.decode('utf-8'))
    event = request_data_dict.get('event')
    if not event:
        logger.error("Received event from slack with no event")
        return "No event", 400

    if event.get('type') != 'link_shared':
        logger.info("Received event that was not link_shared")
        return "Ok", 200

    channel = event.get('channel')
    logger.info("%s action received in channel %s" % (event.get('type'), channel))

    links = event.get('links', None)
    if not links:
        logger.error("No links in event")
        return "No link", 400

    link = links[0]['url']
    link_service = MusicService.from_link(link=link)

    # TODO: change this for cross-service adding
    playlists_in_channel = Playlist.query.filter_by(channel_id=channel, service=link_service).all()

    if not playlists_in_channel:
        return

    successful_playlists = []
    failure_messages = []
    title_or_failure_msg = ""
    title = "(missing title)"
    for pl in playlists_in_channel:
        credentials = pl.user.credentials_for_service(pl.service)
        music_service = ServiceBase.from_enum(pl.service)(credentials=credentials)
        success, title_or_failure_msg = music_service.add_link_to_playlist(pl, link)

        if success:
            title = title_or_failure_msg
            successful_playlists.append(pl.name)
        else:
            failure_messages.append(("%s (%s)" % (pl.name, title_or_failure_msg)))

    response_message = "Something done got real fucked up... you should probably talk to @matt"
    success_message = None
    failure_message = None
    if successful_playlists:
        success_message = "Added %s to playlists: *%s*" % (title, ", ".join(successful_playlists))
    if failure_messages:
        failure_message = "Failed to add track to playlists: *%s*" % (",".join(failure_messages))

    if success_message:
        response_message = success_message
        if failure_message:
            response_message += "\n%s" % failure_message
    elif failure_message:
        response_message = failure_message

    post_update_to_chat(url=SlackUrl.POST_MESSAGE.value,
                        payload={
                            "channel": channel,
                            "text": response_message
                        })
    return "Ok", 200
