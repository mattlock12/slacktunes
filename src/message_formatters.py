import requests

from .constants import SlackUrl
from .music_services import TrackInfo
from settings import SLACK_OAUTH_TOKEN

class SlackMessageFormatter(object):
    @classmethod
    def post_message(cls, payload):
        res = requests.post(
            url=SlackUrl.POST_MESSAGE.value,
            json=payload,
            headers={
                "Content-type": "application/json",
                "Authorization": "Bearer %s" % SLACK_OAUTH_TOKEN
            }
        )

        return res.text, res.status_code

    @classmethod
    def format_results_block(cls, track_info, successes, failures):
        if not successes and not failures:
            return {}
        
        success_str = "*<%s|%s>*" % (track_info.track_open_url(), track_info.get_track_name())
        failure_str = ''

        if successes:
            success_str += "\n\nWas added to playlists:\n"
            successful_playlists = "\n".join([
              "*%s* (%s)" % (pl.name, pl.platform.name.title()) for pl, _
                in successes
            ])
            success_str += successful_playlists
        
        if failures:
            failure_str = "\n\nFailed to add to playlists:\n"
            failed_playlists = "\n".join([
                "*%s* (%s) - %s" % (pl.name, pl.platform.name.title(), reason) for pl, reason
                in failures
            ])
            failure_str += failed_playlists
        

        return  {
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": success_str + failure_str
            },
            "accessory": {
                "type": "image",
                "image_url": track_info.track_image_url(),
                "alt_text": track_info.get_track_name()
            }
        }

    @classmethod
    def format_failed_search_results_message(cls, origin, target_platform):
        if isinstance(origin, TrackInfo):
            origin_link = "*<%s|%s>*" % (origin.track_open_url(), origin.get_track_name())
            attempt_message = "Unable to find %s track for %s" % (
                target_platform.name.title(),
                origin_link
            )
        else:
            attempt_message = "Unable to find %s track for %s" % (
                target_platform.name.title(),
                origin
            )
        
        return {
            'blocks': [
                {
                    "type": "section",
                    "text": {
                        "type": "mrkdwn",
                        "text": attempt_message
                    }
                },
                {
                    "type": "divider"
                }
            ]
        }

    @classmethod
    def format_add_track_results_message(cls, origin, track_info, successes, failures):
        """
        This method assumes that we have successfully found TrackInfo for a shared link or add_track string
        """
        if isinstance(origin, TrackInfo):
            attempt_message = "Attempted match from %s link:\n %s" % (
                origin.platform.name.title(),
                origin.track_open_url()
            )
            
        else:
            attempt_message = "Attempted match for:\n %s" % origin

        return {
            'blocks': [
                cls.format_results_block(track_info=track_info, successes=successes, failures=failures),
                {
                    "type": "context",
                    "elements": [
                        {
                            "type": "mrkdwn",
                            "text": attempt_message
                        }
                    ]
                },
                { "type": "divider" }
            ]
        }
