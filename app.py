import logging
import uuid
from logging.handlers import RotatingFileHandler

from flask import Flask
from flask_sqlalchemy import SQLAlchemy

from settings import DB_URI

application = Flask(__name__)
application.config['SQLALCHEMY_DATABASE_URI'] = DB_URI
application.secret_key = str(uuid.uuid4())
logger = logging.getLogger(__name__)
handler = RotatingFileHandler('slacktunes.log', maxBytes=1000, backupCount=1)
handler.setLevel(logging.INFO)
application.logger.addHandler(handler)
db = SQLAlchemy(application)
