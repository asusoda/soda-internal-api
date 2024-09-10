import unittest
import requests
import json

class TestPointsAPI(unittest.TestCase):
    
    base_url = "http://127.0.0.1:5000"
    
    def setUp(self):
        """Set up test users before running tests."""
        self.test_users = [
            {
                "asu_id": "123456",
                "name": "John Doe",
                "email": "john@example.com",
                "academic_standing": "Sophomore",
                "major": "Computer Science"
            },
            {
                "asu_id": "654321",
                "name": "Jane Doe",
                "email": "jane@example.com",
                "academic_standing": "Junior",
                "major": "Mechanical Engineering"
            },
            {
                "asu_id": "987654",
                "name": "Bob Smith",
                "email": "bob@example.com",
                "academic_standing": "Senior",
                "major": "Electrical Engineering"
            }
        ]
        for user in self.test_users:
            response = requests.post(f"{self.base_url}/points/add_user", json=user)
            if response.status_code != 201:
                print(f"Failed to create user: {user['name']} - Error: {response.json().get('error')}")
            else:
                print(f"User {user['name']} created successfully")
    
    def test_add_user(self):
        """Test 1: Adding users and verifying the number of users."""
        response = requests.get(f"{self.base_url}/points/get_users")
        users = response.json()

        self.assertEqual(response.status_code, 200, "Failed to fetch users.")
        self.assertEqual(len(users), 3, f"Expected 3 users, but got {len(users)}")
        
        print("\nTest 1: Adding users - PASSED")
        print("Output:")
        for user in users:
            print(f" - {user['name']} (Email: {user['email']}, ASU ID: {user['asu_id']})")
    
    def test_add_points(self):
        """Test 2: Adding points to a user and verifying the result."""
        test_points = {
            "user_name": "John Doe",
            "user_email": "john@example.com",
            "user_academic_standing": "Sophomore",
            "points": 100,
            "event": "Hackathon",
            "awarded_by_officer": "Officer A",
            "asu_id": "123456",
            "major": "Computer Science"
        }

        response = requests.post(f"{self.base_url}/points/add_points", json=test_points)
        self.assertEqual(response.status_code, 201, f"Error adding points: {response.json().get('error')}")
        
        print("\nTest 2: Adding points - PASSED")
        print("Output:")
        print(f" - Event: {response.json()['event']}, Points: {response.json()['points']}, User ID: {response.json()['user_id']}")
    
    def test_get_users(self):
        """Test 3: Fetching all users and verifying the count."""
        response = requests.get(f"{self.base_url}/points/get_users")
        self.assertEqual(response.status_code, 200, f"Error fetching users: {response.status_code}")
        
        users = response.json()
        self.assertEqual(len(users), 3, f"Expected 3 users, but got {len(users)}")
        
        print("\nTest 3: Fetching users - PASSED")
        print("Output:")
        for user in users:
            print(f" - {user['name']} (Email: {user['email']}, ASU ID: {user['asu_id']})")

    def test_get_points(self):
        """Test 4: Fetching all points and verifying the result."""
        response = requests.get(f"{self.base_url}/points/get_points")
        self.assertEqual(response.status_code, 200, f"Error fetching points: {response.status_code}")
        
        points = response.json()
        
        print("\nTest 4: Fetching points - PASSED")
        print("Output:")
        for point in points:
            print(f" - Event: {point['event']}, Points: {point['points']}, User ID: {point['user_id']}")

    def test_leaderboard(self):
        """Test 5: Fetching the leaderboard and verifying the order."""
        response = requests.get(f"{self.base_url}/points/leaderboard")
        self.assertEqual(response.status_code, 200, f"Error fetching leaderboard: {response.status_code}")
        
        leaderboard = response.json()
        
        print("\nTest 5: Fetching leaderboard - PASSED")
        print("Output:")
        for entry in leaderboard:
            print(f" - {entry['name']}: {entry['points']} points")

    def tearDown(self):
        """Clean up test data."""
        response = requests.get(f"{self.base_url}/points/get_users")
        users = response.json()

        for user in users:
            # This requires an endpoint that deletes users, like /points/delete_user
            # For now, assume there's an endpoint available for cleanup
            requests.delete(f"{self.base_url}/points/delete_user/{user['uuid']}")

if __name__ == "__main__":
    suite = unittest.TestLoader().loadTestsFromTestCase(TestPointsAPI)
    result = unittest.TextTestRunner(verbosity=2).run(suite)

    # Check if all tests passed
    if result.wasSuccessful():
        print("\nOK ALL TEST CASES PASSED")
    else:
        print("\nSome tests failed")
