from celery import Celery

app = Celery(
    'src',
    broker='redis://redis:6379',
    include=['src.tasks']
)

if __name__ == '__main__':
    app.start()