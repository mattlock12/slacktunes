import requests

from .constants import CS_SEARCH_FAIL_TEMPLATE, SlackUrl
from .models import Playlist, User
from .music_services import ServiceBase, MusicService, TrackInfo

from application import application
from settings import SLACK_OAUTH_TOKEN, SLACKTUNES_USER_ID

"""
Get all links in a channel's history
"""
def get_links(channel_history):
    if not channel_history:
        return []

    return {msg['attachments'][0]['from_url'] for msg in channel_history
            if msg.get('attachments') and
            msg.get('attachments', [])[0] and
            msg['attachments'][0].get('from_url')}

"""
Post a message to a slack room
"""
def post_update_to_chat(payload):
    payload.update({"token": SLACK_OAUTH_TOKEN})
    res = requests.post(url=SlackUrl.POST_MESSAGE.value, data=payload)

    return res.text, res.status_code

"""
Create a MusicService with guaranteed credentials using the slacktunes user
"""
def get_service_from_slacktunes_creds(service):
    user = User.query.filter_by(slack_id=SLACKTUNES_USER_ID).first()
    creds = user.credentials_for_service(service=service)

    return ServiceBase.from_enum(service)(credentials=creds)


def add_link_to_same_service_playlists(playlists, link):
    successes = []
    failures = []
    track_info = None

    for pl in playlists:
        credentials = pl.user.credentials_for_service(pl.service)
        music_service = ServiceBase.from_enum(pl.service)(credentials=credentials)
        success, track_info, message = music_service.add_link_to_playlist(pl, link)

        if success:
            track_info = track_info
            successes.append(message)
        else:
            failures.append(message)

    return track_info, successes, failures


def add_track_to_cross_service_playlists(playlists, track_info):
    successes = []
    failures = []
    cs_track_info = None

    # TODO: there are only 2 services now, so this works. But there may be more in the future
    for cspl in playlists:
        credentials = cspl.user.credentials_for_service(cspl.service)
        music_service = ServiceBase.from_enum(cspl.service)(credentials=credentials)
        cs_track_info = music_service.get_native_track_info_from_track_info(track_info)

        if not cs_track_info:
            failures.append(CS_SEARCH_FAIL_TEMPLATE % (cspl.service.name.title(), track_info.get_track_name()))

        success, _, message = music_service.add_track_to_playlist_by_track_id(cspl, cs_track_info.track_id)

        if success:
            successes.append(message)
        else:
            failures.append(message)

    return cs_track_info, successes, failures


def add_to_playlists_manually(channel_id, artist, track_name, playlist_name=None):
    with application.app_context():
        playlists = Playlist.query.filter_by(channel_id=channel_id)
        if not playlists:
            return post_update_to_chat({
                'text': "No playlists in this channel. Use */create_playlist playlist_name service* to create one",
                'channel_id': channel_id
            })

        if playlist_name:
            playlists = [pl for pl in playlists if pl.name == playlist_name]
            if not playlists:
                return post_update_to_chat({
                    "text": "No playlist found in this channel with name %s" % playlist_name,
                    "channel_id": channel_id
                })

        successes = set()
        failures = set()
        search_services = {}
        infos_by_service = {}
        stub_info = TrackInfo(artist=artist, name=track_name)
        for pl in playlists:
            if not infos_by_service.get(pl.service, None):
                search_service = search_services.get(pl.service, get_service_from_slacktunes_creds(pl.service))
                infos_by_service[pl.service] = search_service.get_native_track_info_from_track_info(track_info=stub_info)

            if not infos_by_service.get(pl.service, None):
                failures.add(
                    CS_SEARCH_FAIL_TEMPLATE % (pl.service.name.title(), "%s -%s" % (artist, track_name))
                )
                continue

            service = ServiceBase.from_enum(pl.service)(credentials=pl.user.credentials_for_service(pl.service))
            success, _, message = service.add_track_to_playlist_by_track_id(
                playlist=pl,
                track_id=infos_by_service.get(pl.service).track_id)

            if success:
                successes.add(message)
            else:
                failures.add(message)


        post_messages_after_link_shared(
            channel=channel_id, native_track_info=stub_info, native_successes=successes, native_failures=failures)


def add_link_to_playlists_from_event(event):
    with application.app_context():
        channel = event.get('channel')
        application.logger.info("%s action received in channel %s" % (event.get('type'), channel))

        links = event.get('links', None)
        if not links:
            application.logger.error("No links in event")
            return "No link", 400

        link = links[0]['url']
        link_service = MusicService.from_link(link=link)

        playlists_in_channel = Playlist.query.filter_by(channel_id=channel).all()
        if not playlists_in_channel:
            return

        native_successes = []
        native_failures = []
        cs_successes = []
        cs_failures = []
        native_track_info = None
        cs_track_info = None

        native_playlists = [pl for pl in playlists_in_channel if pl.service is link_service]
        cross_service_playlists = [cpl for cpl in playlists_in_channel if cpl.service is not link_service]

        if native_playlists:
            native_track_info, native_successes, native_failures = add_link_to_same_service_playlists(
                playlists=native_playlists, link=link)

        # it's possible that there are no native playlists in the channel
        if not native_track_info:
            native_service = get_service_from_slacktunes_creds(link_service)

            if not native_service:
                cs_failures.append("Failed to get service for %s" % link_service.name.title)

                return post_messages_after_link_shared(
                    native_track_info=native_track_info,
                    cs_track_info=cs_track_info,
                    channel=channel,
                    native_successes=native_successes,
                    native_failures=native_failures,
                    cs_successes=cs_successes,
                    cs_failures=cs_failures
                )

            native_track_info = native_service.get_track_info_from_link(link)

        # still can't get track info? Sucks, bro
        if not native_track_info:
            native_failures.append("Couldn't get native track info for track. Unable to share across platforms")
            return post_messages_after_link_shared(
                native_track_info=native_track_info,
                cs_track_info=cs_track_info,
                channel=channel,
                native_successes=native_successes,
                native_failures=native_failures,
                cs_successes=cs_successes,
                cs_failures=cs_failures
            )

        # add to cross_service playlists, using the target service to get track info and add from id after that
        cs_track_info, cs_successes, cs_failures = add_track_to_cross_service_playlists(
            playlists=cross_service_playlists, track_info=native_track_info)

        post_messages_after_link_shared(
            native_track_info=native_track_info,
            cs_track_info=cs_track_info,
            channel=channel,
            native_successes=native_successes,
            native_failures=native_failures,
            cs_successes=cs_successes,
            cs_failures=cs_failures
        )

        return True

def post_messages_after_link_shared(
        native_track_info,
        channel,
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
