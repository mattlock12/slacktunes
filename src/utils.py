import requests

from .constants import SlackUrl
from .models import Credential, Playlist, User
from .music_services import ServiceBase, MusicService

from application import application
from settings import SLACK_OAUTH_TOKEN, SERVICE_SLACK_ID


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
        track_info = None
        message  = ""
        native_track_info = None
        cs_track_info = None

        native_playlists = [pl for pl in playlists_in_channel if pl.service is link_service]
        cross_service_playlists = [cpl for cpl in playlists_in_channel if cpl.service is not link_service]

        # add to native playlists first, to get track info
        for pl in native_playlists:
            credentials = pl.user.credentials_for_service(pl.service)
            music_service = ServiceBase.from_enum(pl.service)(credentials=credentials)
            success, track_info, message = music_service.add_link_to_playlist(pl, link)

            if success:
                native_track_info = track_info
                native_successes.append("%s (%s)" % (pl.name, pl.service.name.title()))
            else:
                native_failures.append("%s (%s) - %s" % (pl.name, pl.service.name.title(), message))

        # it's possible that there are no native playlists in the channel
        if not native_track_info:
            # which means that we don't have track info, and need to get it. Hopefully the user that shared the link
            # has authorized us to use their account
            user = User.query.filter_by(slack_id=event.get('user')).first()
            if not user:
                user = User.query.filter_by(slack_id=SERVICE_SLACK_ID)
            native_creds = user.credentials_for_service(service=link_service)
            if not native_creds:
                cs_failures.append(
                    "No users have authorized %s in this channel, "
                    "so cross platform sharing won't work."
                    " %s should probably run /authorize <service_name> to fix this" %
                    (link_service.name.title(), user.name)
                )

                return post_messages_after_link_shared(
                    native_track_info=native_track_info,
                    cs_track_info=cs_track_info,
                    channel=channel,
                    native_successes=native_successes,
                    native_failures=native_failures,
                    cs_successes=cs_successes,
                    cs_failures=cs_failures
                )

            native_service = ServiceBase.from_enum(link_service)(credentials=native_creds)
            native_track_info = native_service.get_track_info_from_link(link)

        # still can't get track info? Sucks, bro
        if not native_track_info:
            native_failures.append("Couldn't get track info for track... this means cross-platform sharing won't work")
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
        # TODO: there are only 2 services now, so this works. But there may be more in the future
        cs_track_info = None
        for cpl in cross_service_playlists:
            cs_credentials = cpl.user.credentials_for_service(cpl.service)
            cs_music_service = ServiceBase.from_enum(cpl.service)(credentials=cs_credentials)
            cs_track_info = cs_music_service.get_native_track_info_from_track_info(native_track_info)

            if not cs_track_info:
                cs_failures.append('Unable to find %s info for track %s' % (cpl.service.name.title(), native_track_info.get_track_name()))
                return post_messages_after_link_shared(
                    native_track_info=native_track_info,
                    cs_track_info=cs_track_info,
                    channel=channel,
                    native_successes=native_successes,
                    native_failures=native_failures,
                    cs_successes=cs_successes,
                    cs_failures=cs_failures
                )

            success, _, message = cs_music_service.add_track_to_playlist_by_track_id(cpl, cs_track_info.track_id)

            if success:
                cs_successes.append("%s (%s)" % (cpl.name, cpl.service.name.title()))
            else:
                cs_failures.append("%s (%s) - %s" % (cpl.name, cpl.service.name.title(), message))

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
