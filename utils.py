def strip_youtube_video_id(video_url):
    video_id = None
    if "v=" not in video_url:
        # mobile video share
        video_url_parts = video_url.split()
        link = [p for p in video_url_parts if 'yout' in p]
        if not link:
            return None

        return link[0].split('be/')[1]

    video_url.split('?')
    for param in video_url.split('&'):
        if 'v=' in param:
            video_id = param.split('=')[1]
            break
    return video_id


def strip_spotify_track_id(url):
    return url.split('/')[-1]


def get_links(channel_history):
    if not channel_history:
        return []

    return {msg['attachments'][0]['from_url'] for msg in channel_history
            if msg.get('attachments') and
            msg.get('attachments', [])[0] and
            msg['attachments'][0].get('from_url')}
