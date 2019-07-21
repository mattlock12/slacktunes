import celery


@celery.task
def add_track_to_playlists(track_info, playlists):
    pass