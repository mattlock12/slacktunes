from flask_migrate import Migrate

from app import application, db
from src.models import *
from src.views import *

migrate = Migrate(application, db)

if __name__ == '__main__':
    application.run(host='0.0.0.0', port=8000)
