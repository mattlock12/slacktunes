import json

import requests
from flask import render_template, jsonify, redirect, request, url_for
from functools import wraps


from settings import BASE_URI, SLACK_CLIENT_ID, SLACK_CLIENT_SECRET, SLACK_OAUTH_TOKEN, SLACK_VERIFICATION_TOKEN

from app import application, logger
from .constants import InvalidEnumException, Platform, SlackUrl
from .message_formatters import SlackMessageFormatter
from .models import Credential, Playlist, User
from .music_services import ServiceFactory, TrackInfo
from .tasks import add_link_to_playlists, add_links_to_playlist, add_manual_track_to_playlists


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
            return "Not a verified slack message", 400
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
    service = ServiceFactory.from_string(platform_str)
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
    service = ServiceFactory.from_enum(platform_enum)
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
    logger.info("Successfully got credentials from %s" % platform_enum.name.title())

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

    SlackMessageFormatter.post_message(payload={"channel": channel_id, "text": msg_body})

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
               (slack_user_name, BASE_URI, url_for('auth', platform_str=platform_enum.name.lower(), userdata=state))

    credentials = user.credentials_for_platform(platform=platform_enum)
    if not credentials:
        # prompt them to auth on the website
        state = "%s:%s" % (slack_user_id, slack_user_name)
        return "No verified auth for %s. Please go to %s%s and allow access" % \
               (slack_user_name, BASE_URI, url_for('auth', platform_str=platform_enum.name.lower(), userdata=state))

    music_service = ServiceFactory.from_enum(platform_enum)(credentials=credentials)

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


# NOTE: no longer supporting this
@application.route('/scrape_music/', methods=['POST'])
@verified_slack_request
def scrape_music():
    # TODO
    return "Coming soon", 200

    channel_id = request.form['channel_id']
    command_text_args = request.form['text'].split()

    if not len(command_text_args):
        return "Please specify a playlist name in your command", 200

    playlist_name = command_text_args[0]
    playlists = Playlist.query.filter_by(channel_id=channel_id, name=playlist_name).all()
    if not playlists:
        return "No playlist named %s in this channel..." % playlist_name, 200

    if len(command_text_args) > 1:
        pl_platform = Platform.from_string(command_text_args[1])

        playlists = [pl for pl in playlists if pl.platform is pl_platform]    

        if not playlists:
            return "No %s playlist named %s in this channel..." % (pl_platform.name.title(), playlist_name), 200


    playlist = playlists[0]
    user = playlist.user
    if not user or not user.credentials:
        return "Somehow there is no user associated with this playlist... Can't auth with music service", 200

    music_service = ServiceFactory.from_enum(playlist.platform)(credentials=user.credentials_for_platform(playlist.platform))
    # TODO: more robust error handling here
    if playlist.platform_id not in {pl['id'] for pl in music_service.list_playlists()}:
        return "Remote playlist doesn't match local playlist...", 200

    add_links_to_playlist.delay(
        channel_id=channel_id,
        playlist_id=playlist.id
    )

    return "Adding all links in this channel to Playlist %s %s. This might take a minute.", 200


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

    if len(playlist_to_delete) > 1:
        return "More than one playlist matching name %s ... Try specifying the platform" % playlist_name, 200 
    
    playlist_to_delete = playlist_to_delete[0]

    platform = playlist_to_delete.platform
    playlist_to_delete.delete()

    return "Deleted slacktunes record of *%s* in channel *%s* \n" \
        "Keep in mind, this won't delete the %s version, it'll only stop slacktunes" \
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
    filter_kwargs = {
        'channel_id': channel_id
    }

    pl_name_formatted = ""
    if command_text_args:
        playlist_name = command_text_args.pop(0).strip()
        pl_name_formatted = "with name %s" % playlist_name
        filter_kwargs['name'] = playlist_name

    if command_text_args:
        platform_str = command_text_args.pop(0).strip()

    platform_formatted = ""
    if platform_str:
        platform_enum = Platform.from_string(platform_str)
        platform_formatted = "%s " % platform_enum.title()
        filter_kwargs['platform'] = platform_enum

    playlists = Playlist.query.filter_by(**filter_kwargs).all()
    
    if not playlists:
        return "No %splaylists found in channel%s" % (platform_formatted, pl_name_formatted), 200

    # CELERY
    add_manual_track_to_playlists.delay(
        track_name=track_name,
        artist=artist,
        channel_id=channel_id
    )

    return '', 200


# handles incoming event hooks
@application.route("/slack_events/", methods=['POST'])
@verified_slack_request
def slack_events():
    logger.info("Received event")
    if not request.data:
        logger.error("No request data sent to /slack_events")
        return 400

    request_data_dict = json.loads(request.data.decode('utf-8'))
    if request_data_dict.get('challenge'):
        return request_data_dict.get('challenge'), 200

    event = request_data_dict.get('event')
    if not event:
        logger.error("Received event from slack with no event")
        return "No event", 400

    if event.get('type') != 'link_shared':
        logger.info("Received event that was not link_shared")
        return "Ok", 200

    channel = event.get('channel')
    
    links = event.get('links')
    if not links:
        return "No links in event", 200
    
    link = links[0].get('url')
    
    # CELERY
    logger.info("Adding link %s to playilists" % link)
    add_link_to_playlists.delay(
        link=link,
        channel=channel
    )

    return "Ok", 200
