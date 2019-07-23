import requests

from .constants import SlackUrl
from settings import SLACK_OAUTH_TOKEN

class SlackMessageFormatter(object):
    """
    Feed me TrackInfo objects and lists of Tuple(playlist, error_message|None)
    and I will give you formatted messages and POST them to slack
    """
    def __init__(
        self,
        native_track_info=None,
        cross_platform_track_info=None,
        native_platform_successes=None,
        native_platform_failures=None,
        cross_platform_successes=None,
        cross_platform_failures=None
    ):
        self.native_track_info = native_track_info
        self.cross_platform_track_info = cross_platform_track_info
        self.native_platform_successes = native_platform_successes
        self.native_platform_failures = native_platform_failures
        self.cross_platform_successes = cross_platform_successes
        self.cross_platform_failures = cross_platform_failures

    @classmethod
    def post_message(cls, payload):
        payload.update({"token": SLACK_OAUTH_TOKEN})
        res = requests.post(url=SlackUrl.POST_MESSAGE.value, data=payload)

        return res.text, res.status_code

    @classmethod
    def total_failure_message(self, link):
        return {
            "text": "Unable to find info for link %s" % link
        }

    def format_results_block(self, track_info, successes, failures):
        if not successes and not failures:
            return {}
        
        success_str = "*<%s|%s>*" % (track_info.track_open_url(), track_info.get_track_name())
        failure_str = ''

        if successes:
            success_str += "\nWas added to playlists:\n"
            successful_playlists = "\n".join([
              "*%s* (%s)" % (pl.name, pl.platform.name.title()) for pl, _
                in successes
            ])
            success_str += successful_playlists
        
        if failures:
            failure_str = "\nFailed to add to playlists:\n"
            failed_playlists = "\n".join([
                "*%s* (%s) %s" % (pl.name, pl.platform.name.title(), reason) for pl, reason
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
    
    def format_no_results_block(self, cross_platform_track_info):
        return  {
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": "Unable to find %s track for %s\n\nWill schedule another search in 1 week" % (
                    cross_platform_track_info.platform.name.title(),
                    cross_platform_track_info.get_track_name()
                )
            }
        }


    def format_add_link_message(self):
        blocks = []

        # This is the easy part: just show which of the native platform playlists the track
        # was added to (or failed to add to)
        any_native_results_to_display = self.native_platform_failures or self.native_platform_successes
        if any_native_results_to_display:
            blocks.append(self.format_results_block(
                track_info=self.native_track_info,
                successes=self.native_platform_successes,
                failures=self.native_platform_failures
            ))

        # This is a little trickier
        # If we have any native platform results to show, append a divider
        if self.cross_platform_failures or self.cross_platform_successes:
            if any_native_results_to_display:
                blocks.append({"type": "divider"})
            
            # if we found a cross platform equivalent, format it
            if self.cross_platform_track_info:
                blocks.append(self.format_results_block(
                    track_info=self.cross_platform_track_info,
                    successes=self.cross_platform_successes,
                    failures=self.cross_platform_failures
                ))
            else:
                # If not, apologize and promise to do better
                blocks.append(self.format_no_results_block(cross_platform_track_info=self.native_track_info))

            track_link = "*<%s|%s>*" % (self.native_track_info.track_open_url(), self.native_track_info.get_track_name())
            blocks.append({
                "type": "context",
                "elements": [
                    {
                        "type": "mrkdwn",
                        "text": "Attempted match from %s link %s" % (self.native_track_info.platform.name.title(), track_link)
                    }
                ]
            })

        return {
            "blocks": blocks
        }