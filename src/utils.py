import requests

from .constants import SlackUrl
from .models import Playlist
from .music_services import ServiceBase, MusicService
from .views import logger
from settings import SLACK_OAUTH_TOKEN


def get_links(channel_history):
    if not channel_history:
        return []

    return {msg['attachments'][0]['from_url'] for msg in channel_history
            if msg.get('attachments') and
            msg.get('attachments', [])[0] and
            msg['attachments'][0].get('from_url')}


def post_update_to_chat(payload):
    payload.update({"token": SLACK_OAUTH_TOKEN})
    res = requests.post(url=SlackUrl.POST_MESSAGE.value, data=payload)

    return res.text, res.status_code


def add_link_to_playlists_from_event(event):
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

    response_message = ""
    if not successful_playlists and not failure_messages:
        response_message = "Something done got real fucked up... you should probably talk to @matt"

    if successful_playlists:
        response_message += "Added *%s* to playlists: *%s*" % (title, ", ".join(successful_playlists))
    if failure_messages:
        if successful_playlists:
            response_message += "\n"
        response_message += "Failed to add track to playlists: *%s*" % (", ".join(failure_messages))

    post_update_to_chat(
        payload={
            "channel": channel,
            "text": response_message
        }
    )

    return True
