def get_youtube_links(channel_history):
    if not channel_history:
        channel_history = []
    return {msg['attachments'][0]['from_url'] for msg in channel_history
            if msg.get('attachments') and
            msg.get('attachments', [])[0] and
            msg['attachments'][0].get('from_url') and
            'youtube' in msg['attachments'][0].get('from_url')}


def strip_video_id(video_url):
    video_id = None
    video_url.split('?')
    for param in video_url.split('?'):
        if 'v=' in param:
            video_id = param.split('=')[1]
            break
    return video_id