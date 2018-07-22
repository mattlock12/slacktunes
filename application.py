import logging

from app import application
from src.views import *

if __name__ == '__main__':
    logger = logging.getLogger(__name__)
    handler = RotatingFileHandler('slacktunes.log', maxBytes=1000, backupCount=1)
    handler.setLevel(logging.INFO)
    application.logger.addHandler(handler)
    application.run(host='0.0.0.0', port=8000, debug=True)
