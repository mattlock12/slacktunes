def strip_youtube_video_id(video_url):
    video_id = None
    if "v=" not in video_url:
        # mobile video share
        return video_url.split('be/')[1]

    video_url.split('?')
    for param in video_url.split('&'):
        if 'v=' in param:
            video_id = param.split('=')[1]
            break
    return video_id


def get_links(channel_history):
    if not channel_history:
        return []

    return {msg['attachments'][0]['from_url'] for msg in channel_history
            if msg.get('attachments') and
            msg.get('attachments', [])[0] and
            msg['attachments'][0].get('from_url')}
