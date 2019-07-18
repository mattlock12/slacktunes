import unittest


from app import application, db

class DatabaseTestBase(unittest.TestCase):
    def setUp(self):
        db.create_all()

    def tearDown(self):
        # TODO: idk what this does but far be it from me to disobey an SO answer
        db.session.remove()
        db.drop_all()