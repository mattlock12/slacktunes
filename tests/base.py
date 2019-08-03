import os
import unittest

from flask import Flask
from flask_sqlalchemy import SQLAlchemy

from app import application, db


class DatabaseTestBase(unittest.TestCase):

    def setUp(self):
        application.config['TESTING'] = True
        application.config['DEBUG'] = False
        application.config['SQLALCHEMY_DATABASE_URI'] = "sqlite:///test.db"
        db.drop_all()
        db.create_all()

    def tearDown(self):
        # TODO: idk what this does but far be it from me to disobey an SO answer
        db.session.remove()
        db.drop_all()