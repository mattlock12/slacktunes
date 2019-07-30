import requests

from .constants import Platform
from .models import User
from .music_services import ServiceFactory


def get_links(channel_history):
    if not channel_history:
        return []

    return {
        msg['attachments'][0]['from_url'] for msg in channel_history
        if msg.get('attachments') and
        msg.get('attachments', [])[0] and
        msg['attachments'][0].get('from_url')
    }


def get_track_info_from_link(link):
    link_platform = Platform.from_link(link)
    slacktunes_user = User.query.filter_by(is_service_user=True).first()
    slacktunes_creds = slacktunes_user.credentials_for_platform(link_platform)
    slacktunes_same_service = ServiceFactory.from_enum(link_platform)(credentials=slacktunes_creds)

    return slacktunes_same_service.get_track_info_from_link(link=link)


def fuzzy_search_from_string(track_name, artist, platform):
    slacktunes_user = User.query.filter_by(is_service_user=True).first()
    slacktunes_creds = slacktunes_user.credentials_for_platform(platform)
    slacktunes_service = ServiceFactory.from_enum(platform)(credentials=slacktunes_creds)
    
    return slacktunes_service.fuzzy_search(track_name=track_name, artist=artist)


def fuzzy_search_from_track_info(track_info):
    cross_platform = Platform.SPOTIFY if track_info.platform is Platform.YOUTUBE else Platform.YOUTUBE
    slacktunes_user = User.query.filter_by(is_service_user=True).first()
    slacktunes_creds = slacktunes_user.credentials_for_platform(cross_platform)
    slacktunes_cross_service = ServiceFactory.from_enum(cross_platform)(credentials=slacktunes_creds)
    
    return slacktunes_cross_service.fuzzy_search_from_track_info(track_info=track_info)


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
