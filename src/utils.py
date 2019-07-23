import requests

from .constants import Platform, SlackUrl
from .models import Credential, Playlist, User
from .new_services import ServiceBase, ServiceFactory, Platform

from app import logger
from settings import SLACK_OAUTH_TOKEN, SLACKTUNES_USER_ID


def get_links(channel_history):
    if not channel_history:
        return []

    return {msg['attachments'][0]['from_url'] for msg in channel_history
            if msg.get('attachments') and
            msg.get('attachments', [])[0] and
            msg['attachments'][0].get('from_url')}


def post_message_to_chat(payload):
    payload.update({"token": SLACK_OAUTH_TOKEN})
    res = requests.post(url=SlackUrl.POST_MESSAGE.value, data=payload)

    return res.text, res.status_code


def get_track_info_from_link(link):
    link_platform = Platform.from_link(link)
    slacktunes_user = User.query.filter_by(name=SLACKTUNES_USER_ID).first()
    slacktunes_creds = slacktunes_user.credentials_for_platform(link_platform)
    slacktunes_same_service = ServiceFactory.from_enum(link_platform)(credentials=slacktunes_creds)

    return slacktunes_same_service.get_track_info_from_link(link=link)


def fuzzy_search_from_track_info(track_info):
    cross_platform = Platform.SPOTIFY if track_info.platform is Platform.YOUTUBE else Platform.YOUTUBE
    slacktunes_user = User.query.filter_by(name=SLACKTUNES_USER_ID).first()
    slacktunes_creds = slacktunes_user.credentials_for_platform(cross_platform)
    slacktunes_cross_service = ServiceFactory.from_enum(cross_platform)(credentials=slacktunes_creds)
    
    return slacktunes_cross_service.fuzzy_search_for_track(search_string=track_info.get_track_name())


def add_track_to_playlists(track_info, playlists):
    successes = []
    failures = []
    services_by_user = {}
    for pl in playlists:
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
            successes.append((pl, None))
        else:
            failures.append((pl, error_message))
    
    return successes, failures


def add_manual_track_to_playlists(track_info, channel_id, playlist_name=None, platform_str=None):
    playlists = Playlist.query.filter_by(channel_id=channel_id)

    if not playlists:
        return "No playlists in channel! Try /create_playlist", 200

    if playlist_name:
        playlists = playlists.filter_by(name=playlist_name)

    if platform_str:
        playlists = playlists.filter_by(platform=Platform.from_string(platform_str))

    if not playlists:
        return "No %splaylists found with name %s" % (
            "%s " % Platform.from_string(platform_str).name.lower() if platform_str else '',
            playlist_name
        ), 200

    successes = []
    failures = []
    for pl in playlists:
        success, _, error_msg = ServiceBase.from_enum(pl.platform)(
            credentials=pl.user.credentials_for_platform(pl.platform)).add_manual_track_to_playlist(
            playlist=pl,
            track_name=track_info.name,
            artist=track_info.artists)

        if success:
            successes.append("%s (%s)" % (pl.name, pl.platform.name.title()))
        else:
            failures.append("%s (%s) - %s" % (pl.name, pl.platform.name.title(), error_msg))


    return True