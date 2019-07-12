import requests

from .constants import SlackUrl
from .models import Credential, Playlist, User
from .music_services import ServiceBase, MusicService

from application import application
from settings import SLACK_OAUTH_TOKEN, SERVICE_SLACK_ID


def get_links(channel_history):
    if not channel_history:
        return []

    return {
        msg['attachments'][0]['from_url'] for msg in channel_history
        if msg.get('attachments') and
        msg.get('attachments', [])[0] and
        msg['attachments'][0].get('from_url')
    }


def post_update_to_chat(payload):
    payload.update({"token": SLACK_OAUTH_TOKEN})
    res = requests.post(url=SlackUrl.POST_MESSAGE.value, data=payload)

    return res.text, res.status_code


def add_manual_track_to_playlists(track_info, channel_id, playlist_name=None, service_str=None):
    with application.app_context():
        playlists = Playlist.query.filter_by(channel_id=channel_id)

        if not playlists:
            return "No playlists in channel! Try /create_playlist", 200

        if playlist_name:
            playlists = playlists.filter_by(name=playlist_name)

        if service_str:
            playlists = playlists.filter_by(service=MusicService.from_string(service_str))

        if not playlists:
            return "No %splaylists found with name %s" % (
                "%s " % MusicService.from_string(service_str).name.lower() if service_str else '',
                playlist_name
            ), 200

        successes = []
        failures = []
        for pl in playlists:
            success, _, error_msg = ServiceBase.from_enum(pl.service)(
                credentials=pl.user.credentials_for_service(pl.service)).add_manual_track_to_playlist(
                playlist=pl,
                track_name=track_info.name,
                artist=track_info.artists)

            if success:
                successes.append("%s (%s)" % (pl.name, pl.service.name.title()))
            else:
                failures.append("%s (%s) - %s" % (pl.name, pl.service.name.title(), error_msg))

        post_messages_after_link_shared(
            native_track_info=track_info,
            native_successes=successes,
            native_failures=failures,
            channel=channel_id
        )

        return True


def post_messages_after_link_shared(
        native_track_info, channel,
        cs_track_info=None,
        native_successes=None,
        native_failures=None,
        cs_successes=None,
        cs_failures=None):
    native_title = native_track_info.get_track_name()

    response_message = ""
    if not native_successes and not native_failures and not cs_successes and not cs_failures:
        response_message = "Something done got real fucked up... you should probably talk to @matt"

    if native_successes:
        response_message += "Added *%s* to playlists:\n%s" % (native_title, "\n".join("*%s*" % pl for pl in native_successes))
    if native_failures:
        if native_successes:
            response_message += "\n"
        response_message += "Failed to add track to playlists:\n%s" % ("\n".join("*%s*" % msg for msg in native_failures))

    if cs_successes:
        if response_message:
            response_message += "\n"
        response_message += "\nAdded *%s* to playlists:\n%s" % (
            cs_track_info.get_track_name(), "\n".join("*%s*" % pl for pl in cs_successes))
    if cs_failures:
        if response_message:
            response_message += "\n"
        if cs_track_info:
            if native_successes or cs_successes and cs_track_info:
                response_message += "Failed to add track to playlists:\n"
            response_message += ("\n".join("*%s*" % msg for msg in cs_failures))
        else:
            response_message += cs_failures[0]

    post_update_to_chat(
        payload={
            "channel": channel,
            "text": response_message
        }
    )

    return True
