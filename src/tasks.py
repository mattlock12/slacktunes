import collections
import copy
import json

import celery

from src.constants import Platform
from src.models import Playlist, User
from src.message_formatters import SlackMessageFormatter
from src.music_services import ServiceFactory, TrackInfo
from src.utils import (
    add_track_to_playlists,
    fuzzy_search_from_string,
    fuzzy_search_from_track_info,
    get_track_info_from_link
)

app = celery.Celery('tasks', broker="redis://redisbroker:6379/0")


@app.task
def search_and_add_to_playlists(origin, platform, channel):
    """
    1. Search for track info based on target
    2. add to same platform playlists
    """
    platform = Platform.from_string(platform)
    playlists = Playlist.query.filter_by(channel_id=channel, platform=platform).all()
    if not playlists:
        return True

    # see if we were passed a TrackInfo.__dict__
    if 'platform' in origin:
        origin = TrackInfo(**origin)

    if isinstance(origin, TrackInfo):
        best_match = fuzzy_search_from_track_info(track_info=origin)
    else:
        best_match = fuzzy_search_from_string(
            track_name=origin.get('track_name'),
            artist=origin.get('artist'),
            platform=platform
        )

    if not best_match:
        msg_payload = SlackMessageFormatter.format_failed_search_results_message(origin=origin, target_platform=platform)
        msg_payload.update({'channel': channel})
        SlackMessageFormatter.post_message(payload=msg_payload)

        return True

    successes, failures = add_track_to_playlists(
        track_info=best_match,
        playlists=playlists
    )


    # send message
    payload = SlackMessageFormatter.format_add_track_results_message(
        origin=origin,
        track_info=best_match,
        successes=successes,
        failures=failures
    )
    payload.update({'channel': channel})
    SlackMessageFormatter.post_message(payload=payload)

    return True

@app.task
def add_manual_track_to_playlists(track_name, artist, channel):
    origin = {'track_name': track_name, 'artist': artist}
    
    search_and_add_to_playlists.delay(
        origin=origin,
        platform=Platform.YOUTUBE.name,
        channel=channel
    )
    
    search_and_add_to_playlists.delay(
        origin=origin,
        platform=Platform.SPOTIFY.name,
        channel=channel
    )
    
    return True


@app.task
def add_link_to_playlists(link, channel):
    """
    Takes a given link and a list of playlists and:
    1. Gets the TrackInfo from the platform the link was shared from
    2. Schedules an attempt to add TrackInfo to other platform playlistss
    3. Adds the track to all Playlists of the same platform
    """
    link_platform = Platform.from_link(link)

    # Get TrackInfo from native platform
    track_info = get_track_info_from_link(link=link)
    if not track_info:
        # There's something wrong with the link
        msg_payload = SlackMessageFormatter.format_failed_search_results_message(origin=link, target_platform=link_platform)
        msg_payload.update({'channel': channel})
        SlackMessageFormatter.post_message(payload=msg_payload)
        return True
    
    # celery needs json-able objects 
    track_info_json = copy.deepcopy(track_info.__dict__)
    track_info_json['platform'] = track_info.platform.name
    
    # Schedule cross-platform playlists
    search_and_add_to_playlists.delay(
        origin=track_info_json,
        platform=(Platform.SPOTIFY.name if link_platform is Platform.YOUTUBE else Platform.YOUTUBE.name),
        channel=channel
    )

    playlists = Playlist.query.filter_by(channel_id=channel, platform=link_platform).all()
    if not playlists:
        return True
    
    if playlists:
        successes, failures = add_track_to_playlists(
            track_info=track_info,
            playlists=playlists
        )

    # send message
    payload = SlackMessageFormatter.format_add_track_results_message(
        origin=link,
        track_info=track_info,
        successes=successes,
        failures=failures
    )
    payload.update({'channel': channel})
    SlackMessageFormatter.post_message(payload=payload)

    return True
