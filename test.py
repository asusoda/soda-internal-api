import unittest
import json
from modules.points.api import db_connect
from modules.points.models import User, Points
from main import app

class PointsSystemTestCase(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        # Initialize the Flask app and test client
        cls.client = app.test_client()

    def setUp(self):
        # Ensure the database is in a known state before each test
        self.db = next(db_connect.get_db())
        self.db.query(Points).delete()
        self.db.query(User).delete()
        self.db.commit()

    def tearDown(self):
        # Clean up the database after each test
        self.db.query(Points).delete()
        self.db.query(User).delete()
        self.db.commit()
        self.db.close()

    def test_add_user(self):
        user_data = {
            'name': 'John Doe',
            'email': 'john.doe@example.com',
            'academic_standing': 'Senior'
        }
        response = self.client.post('/points-system/users', data=json.dumps(user_data), content_type='application/json')
        self.assertEqual(response.status_code, 201)
        response_data = json.loads(response.data)
        self.assertIn('uuid', response_data)
        self.assertEqual(response_data['name'], 'John Doe')
        self.assertEqual(response_data['email'], 'john.doe@example.com')
        self.assertEqual(response_data['academic_standing'], 'Senior')

    def test_add_point_for_existing_user(self):
        user_data = {
            'name': 'John Doe',
            'email': 'john.doe@example.com',
            'academic_standing': 'Senior'
        }
        user_response = self.client.post('/points-system/users', data=json.dumps(user_data), content_type='application/json')
        user_uuid = json.loads(user_response.data)['uuid']

        point_data = {
            'points': 10,
            'event': 'Hackathon',
            'awarded_by_officer': 'Jane Smith',
            'user_id': user_uuid
        }
        response = self.client.post('/points-system/points', data=json.dumps(point_data), content_type='application/json')
        self.assertEqual(response.status_code, 201)
        response_data = json.loads(response.data)
        self.assertIn('id', response_data)
        self.assertEqual(response_data['points'], 10)
        self.assertEqual(response_data['event'], 'Hackathon')
        self.assertEqual(response_data['awarded_by_officer'], 'Jane Smith')
        self.assertEqual(response_data['user_id'], user_uuid)

    def test_add_point_for_new_user(self):
        point_data = {
            'points': 10,
            'event': 'Hackathon',
            'awarded_by_officer': 'Jane Smith',
            'user_name': 'John Doe',
            'user_email': 'john.doe@example.com',
            'user_academic_standing': 'Senior'
        }
        response = self.client.post('/points-system/points', data=json.dumps(point_data), content_type='application/json')
        self.assertEqual(response.status_code, 201)
        response_data = json.loads(response.data)
        self.assertIn('id', response_data)
        self.assertEqual(response_data['points'], 10)
        self.assertEqual(response_data['event'], 'Hackathon')
        self.assertEqual(response_data['awarded_by_officer'], 'Jane Smith')
        self.assertIn('user_id', response_data)

    def test_get_users(self):
        user_data = {
            'name': 'John Doe',
            'email': 'john.doe@example.com',
            'academic_standing': 'Senior'
        }
        self.client.post('/points-system/users', data=json.dumps(user_data), content_type='application/json')
        response = self.client.get('/points-system/users')
        self.assertEqual(response.status_code, 200)
        response_data = json.loads(response.data)
        self.assertEqual(len(response_data), 1)
        self.assertEqual(response_data[0]['name'], 'John Doe')
        self.assertEqual(response_data[0]['email'], 'john.doe@example.com')
        self.assertEqual(response_data[0]['academic_standing'], 'Senior')

    def test_get_points(self):
        user_data = {
            'name': 'John Doe',
            'email': 'john.doe@example.com',
            'academic_standing': 'Senior'
        }
        user_response = self.client.post('/points-system/users', data=json.dumps(user_data), content_type='application/json')
        user_uuid = json.loads(user_response.data)['uuid']

        point_data = {
            'points': 10,
            'event': 'Hackathon',
            'awarded_by_officer': 'Jane Smith',
            'user_id': user_uuid
        }
        self.client.post('/points-system/points', data=json.dumps(point_data), content_type='application/json')

        response = self.client.get('/points-system/points')
        self.assertEqual(response.status_code, 200)
        response_data = json.loads(response.data)
        self.assertEqual(len(response_data), 1)
        self.assertEqual(response_data[0]['points'], 10)
        self.assertEqual(response_data[0]['event'], 'Hackathon')
        self.assertEqual(response_data[0]['awarded_by_officer'], 'Jane Smith')
        self.assertEqual(response_data[0]['user_id'], user_uuid)

if __name__ == '__main__':
    unittest.main()
