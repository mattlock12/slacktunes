import collections

import celery

from src.constants import Platform
from src.models import Playlist, User
from src.message_formatters import SlackMessageFormatter
from src.new_services import ServiceFactory
from src.utils import add_track_to_playlists, fuzzy_search_from_track_info, get_track_info_from_link
from settings import SLACKTUNES_USER_ID


@celery.task
def add_link_to_playlists(link, playlists, channel, formatter_class=SlackMessageFormatter):
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
    track_info = get_track_info_from_link(link=link)
    if not track_info:
        # There's something wrong with the link
        msg_payload.update(formatter_class.total_failure_message(link=link))
        formatter_class.post_message(payload=msg_payload)
        return True
        
    # Initialize some objects to hold results
    formatter = formatter_class(native_track_info=track_info)
    
    """
    STEP 2. Add track to same platform playlists
    """
    # reduce overhead by memoizing services of the same platform for a user
    native_playlists = playlists_by_platform.get(link_platform)
    if native_playlists:
        native_successes, native_failures = add_track_to_playlists(
            track_info=track_info,
            playlists=native_playlists
        )
        formatter.native_platform_successes = native_successes
        formatter.native_platform_failures = native_failures

    """
    STEP 3. Use the TrackInfo to search for a similar track in the other platform
    """
    cross_platform = Platform.SPOTIFY if link_platform is Platform.YOUTUBE else Platform.YOUTUBE
    # no need to do all this work for nothing
    if not playlists_by_platform[cross_platform]:
        msg_payload.update(formatter.format_add_link_message())
        formatter.post_message(payload=msg_payload)
        
        return True
    
    best_match = fuzzy_search_from_track_info(track_info=track_info)
    if not best_match:
        formatter.cross_platform_failures = [(cpl, "No matching track found") for cpl in playlists_by_platform[cross_platform]]
        msg_payload.update(formatter.format_add_link_message())
        formatter.post_message(payload=msg_payload)

        return True

    """
    STEP 4. Add best_match (a TrackInfo object) to cross-platform playlists
    """
    cp_successes, cp_failures = add_track_to_playlists(
        track_info=best_match,
        playlists=playlists_by_platform.get(cross_platform)
    )
    formatter.cross_platform_track_info = best_match
    formatter.cross_platform_successes = cp_successes
    formatter.cross_platform_failures = cp_failures

    msg_payload.update(formatter.format_add_link_message())
    formatter.post_message(payload=msg_payload)

    return True