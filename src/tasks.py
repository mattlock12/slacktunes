import collections
import copy
import json

import celery
import requests

from src.constants import Platform, SlackUrl
from src.models import Playlist, User
from src.message_formatters import SlackMessageFormatter
from src.music_services import ServiceFactory, TrackInfo
from src.utils import (
    add_track_to_playlists,
    get_links,
    fuzzy_search_from_string,
    fuzzy_search_from_track_info,
    get_track_info_from_link
)
from settings import SLACK_OAUTH_TOKEN

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


@app.task
def add_links_to_playlist(channel_id, playlist_id):
    playlist = Playlist.query.filter_by(id=playlist_id).first()
    if not playlist:
        SlackMessageFormatter.post_message(
            payload={
                'channel': channel_id,
                'text': 'No playlist in this channel with id %s' % playlist_id
            }
        )
        return False

    history_payload = {
        "token": SLACK_OAUTH_TOKEN,
        "channel": channel_id,
        "count": 1000
    }
    channel_history = requests.post(url=SlackUrl.CHANNEL_HISTORY.value, data=history_payload)
    channel_history_jsonable = channel_history.json().get('messages')

    links = get_links(channel_history=channel_history_jsonable)
    """
    Links will either be same or cross platform
    If same, get the id and add
    If cross platform, search and add by id
    """
    playlist_music_service = ServiceFactory.from_enum(playlist.platform)(
        credentials=playlist.user.credentials_for_platform(playlist.platform)
    )
    cross_platform = Platform.YOUTUBE if playlist.platform is Platform.SPOTIFY else Platform.SPOTIFY
    slacktunes_service_user = User.query.filter_by(is_service_user=True).first()
    slacktunes_service_credentials = slacktunes_service_user.credentials_for_platform(platform=cross_platform)
    cross_platform_slacktunes_service = ServiceFactory.from_enum(cross_platform)(
        credentials=slacktunes_service_credentials)
    

    successes = 0
    failures = 0
    for link in links:
        link_platform = Platform.from_link(link)

        if link_platform is playlist.platform:
            track_info = playlist_music_service.get_track_info_from_link(link=link)
            success, _ = playlist_music_service.add_track_to_playlist(
                track_info=track_info,
                playlist=playlist
            )
        else:
            cross_track_info = cross_platform_slacktunes_service.get_track_info_from_link(link=link)
            best_match = fuzzy_search_from_track_info(
                track_info=cross_track_info,
                slacktunes_cross_service=cross_platform_slacktunes_service
            )
            if not best_match:
                success = False
            else:
                success, _ = playlist_music_service.add_track_to_playlist(
                    track_info=best_match,
                    playlist=playlist
                )
        if success:
            successes += 1
        else:
            failures += 1
    
    SlackMessageFormatter.post_message(payload={
        'channel': channel_id,
        'text': "Finished scraping music for %s (%s)\nSuccessfully added %s tracks\nFailed to add %s tracks" % (
            playlist.name,
            playlist.platform.title(),
            successes,
            failures
        )
    })

    return True