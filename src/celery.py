from celery import Celery

celery_app = Celery(
    'src',
    broker='redis://redis:6379',
    include=['src.tasks']
)

if __name__ == '__main__':
    celery_app.start()