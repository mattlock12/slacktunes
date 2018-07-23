import uuid

from flask import Flask
from flask_sqlalchemy import SQLAlchemy

from settings import DB_URI

application = Flask(__name__)
application.config['SQLALCHEMY_DATABASE_URI'] = DB_URI
application.secret_key = str(uuid.uuid4())
db = SQLAlchemy(application)