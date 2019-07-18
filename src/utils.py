import requests

from .constants import SlackUrl
from .models import Credential, Playlist, User
from .music_services import ServiceBase, Platform

from settings import SLACK_OAUTH_TOKEN, SERVICE_SLACK_ID


def post_message_to_slack(payload):
    payload.update({"token": SLACK_OAUTH_TOKEN})
    res = requests.post(url=SlackUrl.POST_MESSAGE.value, data=payload)

    return res.text, res.status_code


def get_links(channel_history):
    if not channel_history:
        return []

    return {
        msg['attachments'][0]['from_url'] for msg in channel_history
        if msg.get('attachments') and
        msg.get('attachments', [])[0] and
        msg['attachments'][0].get('from_url')
    }


def add_manual_track_to_playlists(track_info, channel_id, playlist_name=None, service_str=None):
    # playlists = Playlist.query.filter_by(channel_id=channel_id)

    # if not playlists:
    #     return "No playlists in channel! Try /create_playlist", 200

    # if playlist_name:
    #     playlists = playlists.filter_by(name=playlist_name)

    # if service_str:
    #     playlists = playlists.filter_by(service=Platform.from_string(service_str))

    # if not playlists:
    #     return "No %splaylists found with name %s" % (
    #         "%s " % Platform.from_string(service_str).name.lower() if service_str else '',
    #         playlist_name
    #     ), 200

    # successes = []
    # failures = []
    # for pl in playlists:
    #     success, _, error_msg = ServiceBase.from_enum(pl.service)(
    #         credentials=pl.user.credentials_for_service(pl.service)).add_manual_track_to_playlist(
    #         playlist=pl,
    #         track_name=track_info.name,
    #         artist=track_info.artists)

    #     if success:
    #         successes.append("%s (%s)" % (pl.name, pl.service.name.title()))
    #     else:
    #         failures.append("%s (%s) - %s" % (pl.name, pl.service.name.title(), error_msg))

    # post_messages_after_link_shared(
    #     native_track_info=track_info,
    #     native_successes=successes,
    #     native_failures=failures,
    #     channel=channel_id
    # )

    return True


def post_messages_after_link_shared(self, *args, **kwargs):
    pass
