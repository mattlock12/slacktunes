from app import application, db
from src.models import *
from src.views import *

def create_tables():
    db.create_all()


if __name__ == '__main__':
    create_tables()
    application.run(host='0.0.0.0', port=8000)
