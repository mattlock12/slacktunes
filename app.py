import logging
import uuid

from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate

from settings import DB_URI

application = Flask(__name__)
application.config['SQLALCHEMY_DATABASE_URI'] = DB_URI
application.secret_key = str(uuid.uuid4())
logger = logging.getLogger(__name__)
handler = logging.StreamHandler()
handler.setLevel(logging.INFO)
application.logger.addHandler(handler)
db = SQLAlchemy(application)

migrate = Migrate(application, db)
