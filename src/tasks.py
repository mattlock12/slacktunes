import collections
from typing import List

from redis import Redis

from app import logger
from .celery import celery_app
from .models import User, Playlist
from .message_formatters import SlackMessageFormatter
# from .music_services import Platform, ServiceFactory
from .new_services import Platform, ServiceFactory
from .utils import post_message_to_slack
from settings import SERVICE_SLACK_ID


@celery_app.task
def add_link_to_playlists(link: str, playlists: List, channel: str) -> str:
    """
    Takes a given link and a list of playlists and:
    1. Gets the TrackInfo from the platform the link was shared from
    2. Adds the track to all Playlists of the same platform
    3. Attempts to get matching TrackInfo from the other platform
    4. Adds the cross-platform TrackInfo to all cross-platform Playlists
    """
    link_platform = Platform.from_link(link)
    msg_payload = {
        'channel': channel
    }

    playlists_by_platform = collections.defaultdict(list)
    for pl in playlists:
        playlists_by_platform[pl.platform].append(pl)

    """
    STEP 1. Get TrackInfo from native platform
    """
    slacktunes_user = User.query.filter_by(name=SERVICE_SLACK_ID)
    slacktunes_creds = slacktunes_user.credentials_for_platform(link_platform)
    slacktunes_same_service = ServiceFactory.from_enum(link_platform)(credentials=slacktunes_creds)

    track_info = slacktunes_same_service.get_track_info_from_link(link=link)
    if not track_info:
        # There's something wrong with the link
        msg_payload.update(SlackMessageFormatter.total_failure_message(link=link))
        post_message_to_slack(payload=msg_payload)
        return True
        
    # Initialize some objects to hold results
    formatter = SlackMessageFormatter(native_track_info=track_info)
    native_successes = []
    native_failures = []
    cp_successes = []
    cp_failures = []
    
    """
    STEP 2. Add track to same platform playlists
    """
    # reduce overhead by memoizing services of the same platform for a user
    services_by_user = {}
    for pl in playlists_by_platform[link_platform]:
        pl_service = services_by_user.get(pl.user)
        if not pl_service:
            pl_creds = pl.user.credentials_for_platform(platform=pl.platform)
            pl_service = ServiceFactory.from_enum(pl.platform)(credentials=pl_creds)
            services_by_user[pl.user] = pl_service
        
        success, error_message = pl_service.add_track_to_playlist(track_info=track_info, playlist=pl)
        # NOTE: Error message will be None if success == True
        # Don't do anything fancy (like schedle a retry) on failure here because same-service failures are probably
        # network failures, malformed requests, or some other thing that is beyond our control
        if success:
            native_successes.append((pl, None))
        else:
            native_failures.append((pl, error_message))
    
    formatter.native_platform_successes = native_successes
    formatter.native_platform_failures = native_failures

    """
    STEP 3. Use the TrackInfo to search for a similar track in the other platform
    """
    cross_platform = Platform.SPOTIFY if link_platform is Platform.YOUTUBE else Platform.YOUTUBE
    # no need to do all this work for nothing
    if not playlists_by_platform[cross_platform]:
        msg_payload.update(formatter.format_add_link_message())
        post_message_to_slack(payload=msg_payload)
        
        return True

    slacktunes_cross_platform_creds = slacktunes_user.credentials_for_platform(cross_platform)
    slacktunes_cross_service = ServiceFactory.from_enum(cross_platform)(credentials=slacktunes_cross_platform_creds)
    
    best_match = slacktunes_cross_service.fuzzy_search_for_track(search_string=track_info.get_track_name())
    if not best_match:
        formatter.cross_platform_failures = [(cpl, "No matching track found") for cpl in playlists_by_platform[cross_platform]]
        msg_payload.update(formatter.format_add_link_message())
        post_message_to_slack(payload=msg_payload)

        return True

    """
    STEP 4. Add best_match (a TrackInfo object) to cross-platform playlists
    """
    cp_services_by_user = {}
    for cppl in playlists_by_platform[cross_platform]:
        cp_service = cp_services_by_user[cppl.user]
        if not cp_service:
            cp_creds = pl.user.credentials_for_platform(platform=cppl.platform)
            cp_service = ServiceFactory.from_enum(cppl.platform)(credentials=cp_creds)
            cp_services_by_user[cppl.user] = cp_service
        
        success, error_message = cp_service.add_track_to_playlist(track_info=best_match, playlist=cppl)
        # NOTE: error_message is None when success == True
        if success:
            cp_successes.append((cppl, None))
        else:
            cp_failures.append((cppl, error_message))
    
    formatter.cross_platform_track_info = best_match
    formatter.cross_platform_successes = cp_successes
    formatter.cross_platform_failures = cp_failures
    msg_payload.update(formatter.format_add_link_message())
    post_message_to_slack(payload=msg_payload)

    return True
        

# @celery_app.task
# def add_link_to_playlists_from_event(event):
#     channel = event.get('channel')
#     logger.info("%s action received in channel %s" % (event.get('type'), channel))

#     links = event.get('links', None)
#     if not links:
#         logger.error("No links in event")
#         return "No link", 400

#     link = links[0]['url']
#     link_service = Platform.from_link(link=link)

#     playlists_in_channel = Playlist.query.filter_by(channel_id=channel).all()
#     if not playlists_in_channel:
#         return

#     native_successes = []
#     native_failures = []
#     cs_successes = []
#     cs_failures = []
#     track_info = None
#     message  = ""
#     native_track_info = None
#     cs_track_info = None

#     native_playlists = [pl for pl in playlists_in_channel if pl.service is link_service]
#     cross_service_playlists = [cpl for cpl in playlists_in_channel if cpl.service is not link_service]

#     # add to native playlists first, to get track info
#     for pl in native_playlists:
#         credentials = pl.user.credentials_for_servplatformservice
#         music_service = ServiceFactory.from_enum(pl.service)(credentials=credentials)
#         success, track_info, message = music_service.add_link_to_playlist(pl, link)

#         if success:
#             native_track_info = track_info
#             native_successes.append("%s (%s)" % (pl.name, pl.service.name.title()))
#         else:
#             native_failures.append("%s (%s) - %s" % (pl.name, pl.service.name.title(), message))

#     # it's possible that there are no native playlists in the channel
#     if not native_track_info:
#         # which means that we don't have track info, and need to get it. Hopefully the user that shared the link
#         # has authorized us to use their account
#         user = User.query.filter_by(slack_id=event.get('user')).first()
#         # if not, use the backup service user
#         if not user:
#             user = User.query.filter_by(slack_id=SERVICE_SLACK_ID)
#         native_creds = user.credentials_for_service(service=link_service)
#         if not native_creds:
#             cs_failures.append(
#                 "No users have authorized %s in this channel, "
#                 "so cross platform sharing won't work."
#                 " %s should probably run /authorize <service_name> to fix this" %
#                 (link_service.name.title(), user.name)
#             )

#             return post_messages_after_link_shared(
#                 native_track_info=native_track_info,
#                 cs_track_info=cs_track_info,
#                 channel=channel,
#                 native_successes=native_successes,
#                 native_failures=native_failures,
#                 cs_successes=cs_successes,
#                 cs_failures=cs_failures
#             )

#         native_service = ServiceFactory.from_enum(link_service)(credentials=native_creds)
#         native_track_info = native_service.get_track_info_from_link(link)

#     # still can't get track info? Sucks, bro
#     if not native_track_info:
#         native_failures.append("Couldn't get track info for track... this means cross-platform sharing won't work")
#         return post_messages_after_link_shared(
#             native_track_info=native_track_info,
#             cs_track_info=cs_track_info,
#             channel=channel,
#             native_successes=native_successes,
#             native_failures=native_failures,
#             cs_successes=cs_successes,
#             cs_failures=cs_failures
#         )

#     # add to cross_service playlists, using the target service to get track info and add from id after that
#     # TODO: there are only 2 services now, so this works. But there may be more in the future
#     cs_track_info = None
#     for cpl in cross_service_playlists:
#         cs_credentials = cpl.user.credentials_for_service(cpl.service)
#         cs_music_service = ServiceFactory.from_enum(cpl.service)(credentials=cs_credentials)
#         cs_track_info = cs_music_service.get_native_track_info_from_track_info(native_track_info)

#         if not cs_track_info:
#             cs_failures.append('Unable to find %s info for track %s' % (cpl.service.name.title(), native_track_info.get_track_name()))
#             return post_messages_after_link_shared(
#                 native_track_info=native_track_info,
#                 cs_track_info=cs_track_info,
#                 channel=channel,
#                 native_successes=native_successes,
#                 native_failures=native_failures,
#                 cs_successes=cs_successes,
#                 cs_failures=cs_failures
#             )

#         success, _, message = cs_music_service.add_track_to_playlist_by_track_id(cpl, cs_track_info.track_id)

#         if success:
#             cs_successes.append("%s (%s)" % (cpl.name, cpl.service.name.title()))
#         else:
#             cs_failures.append("%s (%s) - %s" % (cpl.name, cpl.service.name.title(), message))

#     post_messages_after_link_shared(
#         native_track_info=native_track_info,
#         cs_track_info=cs_track_info,
#         channel=channel,
#         native_successes=native_successes,
#         native_failures=native_failures,
#         cs_successes=cs_successes,
#         cs_failures=cs_failures
#     )

#     return True
