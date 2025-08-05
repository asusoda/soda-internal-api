import requests
import json
import time

# --- Configuration ---
BASE_URL = "http://127.0.0.1:8000"  # ADJUST IF YOUR APP RUNS ON A DIFFERENT PORT/URL
TEST_TOKEN = "YOUR_VALID_TEST_TOKEN"  # REPLACE WITH A VALID JWT TOKEN FOR AUTHENTICATED ENDPOINTS
# To get a test token, you might need to manually go through the login flow once
# and extract the token your frontend receives, or have a debug endpoint to generate one.

DEFAULT_HEADERS = {
    "Content-Type": "application/json",
    "Authorization": f"Bearer {TEST_TOKEN}"
}

NO_AUTH_HEADERS = {
    "Content-Type": "application/json"
}

# --- Global Test Counters & Details ---
passed_tests = 0
failed_tests = 0
failed_test_details = [] # Stores info about failed tests

# --- Helper Function ---
def make_request(method, endpoint, headers=None, params=None, data=None, description=""):
    global passed_tests, failed_tests, failed_test_details
    url = f"{BASE_URL}{endpoint}"
    print(f"--- Testing: {description} ({method.upper()} {endpoint}) ---")
    # Removed verbose request details printing here to reduce noise for passed tests
    
    test_passed_this_call = False
    status_code_for_report = None
    response_preview_for_report = "N/A"

    try:
        response = requests.request(method, url, headers=headers, params=params, json=data if isinstance(data, dict) else None, data=data if not isinstance(data, dict) else None, timeout=10)
        status_code_for_report = response.status_code

        try:
            response_json = response.json()
            response_preview_for_report = json.dumps(response_json)[:200] # Preview of JSON
            # Only print detailed response if test might fail or has warning
            if response.status_code >= 400 and "error" not in response_json and "message" not in response_json:
                # This warning will still print for failed tests if condition met
                pass # Detailed print will happen if assertion fails
        except ValueError:
            response_preview_for_report = response.text[:200] # Preview of text
            if response.status_code < 400:
                # This warning will still print for failed tests if condition met
                pass # Detailed print will happen if assertion fails

        # Assertion logic
        try:
            if "error" in description.lower() or "invalid" in description.lower() or "unauthorized" in description.lower():
                assert response.status_code >= 400, f"Expected error status code (>=400), got {response.status_code}"
            elif endpoint == "/auth/login": 
                assert response.status_code == 200 or response.status_code == 302, f"Expected 200 or 302 for /auth/login, got {response.status_code}"
            else: 
                assert response.status_code < 400, f"Expected success status code (<400), got {response.status_code}"
            test_passed_this_call = True 
        except AssertionError as ae:
            # Detailed print only on assertion failure
            print(f"Request: {method.upper()} {url}")
            if params: print(f"Params: {params}")
            if data: print(f"Data: {json.dumps(data) if isinstance(data, dict) else data}")
            print(f"Status Code: {status_code_for_report}")
            try: print(f"Response JSON: {json.dumps(response.json(), indent=2)}")
            except: print(f"Response Text: {response.text}")
            print(f"Assertion FAILED: {ae}")

    except requests.exceptions.RequestException as e:
        # Detailed print only on request exception
        print(f"Request: {method.upper()} {url}")
        if params: print(f"Params: {params}")
        if data: print(f"Data: {json.dumps(data) if isinstance(data, dict) else data}")
        print(f"Request FAILED: {e}")
        response_preview_for_report = str(e)[:200]
    finally:
        if test_passed_this_call:
            passed_tests += 1
            print("Status: PASSED")
        else:
            failed_tests += 1
            print("Status: FAILED")
            failed_test_details.append({
                "description": description,
                "method": method.upper(),
                "url": url,
                "status_code": status_code_for_report,
                "response_preview": response_preview_for_report + ("..." if len(response_preview_for_report) == 200 else "")
            })
        print("----------------------------") # Removed newline for cleaner summary
        time.sleep(0.05) # Reduced sleep time slightly

# --- Test Functions for Each Module ---

def test_auth_endpoints():
    print("\n========== Testing Auth Endpoints ==========")
    make_request("GET", "/auth/login", headers=NO_AUTH_HEADERS, description="Auth Login Redirect")
    
    # /validToken - This is a typo in your backend (should be /validateToken or similar based on usage)
    # Assuming it's /validateToken as defined later
    # make_request("GET", "/auth/validToken", headers=DEFAULT_HEADERS, description="Auth Valid Token (Corrected to /validateToken below)")

    make_request("GET", "/auth/callback", headers=NO_AUTH_HEADERS, params={"code": "test_auth_code"}, description="Auth Callback with code")
    make_request("GET", "/auth/callback", headers=NO_AUTH_HEADERS, description="Auth Callback without code (expect error)")

    make_request("GET", "/auth/validateToken", headers=DEFAULT_HEADERS, description="Auth Validate Token - Valid Token")
    make_request("GET", "/auth/validateToken", headers={"Authorization": "Bearer INVALID_TOKEN", "Content-Type": "application/json"}, description="Auth Validate Token - Invalid Token (expect error)")
    # Test for expired token would require a way to generate/get an expired one

    make_request("GET", "/auth/refresh", headers=DEFAULT_HEADERS, description="Auth Refresh Token (assuming token is not expired)")
    # Test with an expired token would require specific setup

    make_request("GET", "/auth/appToken", headers=DEFAULT_HEADERS, params={"appname": "test_app"}, description="Auth Generate App Token")
    make_request("GET", "/auth/appToken", headers=DEFAULT_HEADERS, description="Auth Generate App Token - Missing appname (expect error)")
    
    make_request("GET", "/auth/name", headers=DEFAULT_HEADERS, description="Auth Get Name")
    make_request("GET", "/auth/logout", headers=DEFAULT_HEADERS, description="Auth Logout")
    make_request("GET", "/auth/success", headers=NO_AUTH_HEADERS, description="Auth Success Page")

def test_points_endpoints():
    print("\n========== Testing Points Endpoints ==========")
    make_request("GET", "/points/", headers=NO_AUTH_HEADERS, description="Points Index") # Assuming no auth, adjust if needed

    user_data_good = {"email": f"testuser_{int(time.time())}@example.com", "asu_id": "1234567890", "name": "Test User", "academic_standing": "Senior", "major": "CS"}
    make_request("POST", "/points/add_user", headers=DEFAULT_HEADERS, data=user_data_good, description="Points Add User - New")
    make_request("POST", "/points/add_user", headers=DEFAULT_HEADERS, data=user_data_good, description="Points Add User - Duplicate (expect error/specific code)") # Test duplicate

    points_data = {"user_email": user_data_good["email"], "points": 10, "event": "Test Event", "awarded_by_officer": "Test Officer"}
    make_request("POST", "/points/add_points", headers=DEFAULT_HEADERS, data=points_data, description="Points Add Points - Existing User")
    make_request("POST", "/points/add_points", headers=DEFAULT_HEADERS, data={"user_email": "nonexistent@example.com", "points": 5, "event": "Another Event", "awarded_by_officer": "Test Officer"}, description="Points Add Points - Non-existent User (expect error)")

    make_request("GET", "/points/get_users", headers=DEFAULT_HEADERS, description="Points Get Users")
    make_request("GET", "/points/get_points", headers=DEFAULT_HEADERS, description="Points Get Points")
    
    make_request("GET", "/points/leaderboard", headers=NO_AUTH_HEADERS, description="Points Leaderboard - No Auth")
    make_request("GET", "/points/leaderboard", headers=DEFAULT_HEADERS, description="Points Leaderboard - With Auth (shows email)")

    # File upload is complex for a simple script, sending minimal form data
    form_data_csv = {'event_name': 'CSV Event', 'event_points': '15'} # 'file' part missing
    # make_request("POST", "/points/uploadEventCSV", headers={"Authorization": f"Bearer {TEST_TOKEN}"}, data=form_data_csv, description="Points Upload Event CSV (Simplified - no actual file)")
    print("Skipping /points/uploadEventCSV test as it requires actual file upload.")


    make_request("GET", "/points/getUserPoints", headers=DEFAULT_HEADERS, params={"email": user_data_good["email"]}, description="Points Get User Points - Existing User")
    make_request("GET", "/points/getUserPoints", headers=DEFAULT_HEADERS, params={"email": "nonexistent@example.com"}, description="Points Get User Points - Non-existent User (expect error)")

    assign_points_data = {"user_identifier": user_data_good["email"], "points": 5, "event": "Assigned Event", "awarded_by_officer": "Admin"}
    make_request("POST", "/points/assignPoints", headers=DEFAULT_HEADERS, data=assign_points_data, description="Points Assign Points")

    delete_points_data = {"user_email": user_data_good["email"], "event": "Test Event"} # Assuming "Test Event" was added
    make_request("DELETE", "/points/delete_points", headers=DEFAULT_HEADERS, data=delete_points_data, description="Points Delete Points by Event")


def test_public_endpoints():
    print("\n========== Testing Public Endpoints ==========")
    # /getnextevent seems to be a stub in modules/public/api.py
    make_request("GET", "/public/getnextevent", headers=NO_AUTH_HEADERS, description="Public Get Next Event")
    
    # This leaderboard is different from /points/leaderboard
    make_request("GET", "/public/leaderboard", headers=NO_AUTH_HEADERS, description="Public Leaderboard")

    # Test serving static files (index.html)
    make_request("GET", "/", headers=NO_AUTH_HEADERS, description="Public Serve Static - Root (index.html)")
    # make_request("GET", "/manifest.json", headers=NO_AUTH_HEADERS, description="Public Serve Static - manifest.json") # Example


def test_calendar_endpoints():
    print("\n========== Testing Calendar Endpoints (including OCP) ==========")
    make_request("POST", "/calendar/notion-webhook", headers=NO_AUTH_HEADERS, data={}, description="Calendar Notion Webhook")
    make_request("GET", "/calendar/events", headers=NO_AUTH_HEADERS, description="Calendar Get Events for Frontend")
    
    # Destructive operation - call with caution or ensure ALLOW_DELETE_ALL is false for safety in prod/staging
    make_request("POST", "/calendar/delete-all-events", headers=NO_AUTH_HEADERS, data={}, description="Calendar Delete All Events (Potentially Destructive - expect error if not configured/allowed)")

    # OCP Endpoints (prefixed with /ocp)
    ocp_prefix = "/ocp"
    make_request("POST", f"{ocp_prefix}/sync-from-notion", headers=NO_AUTH_HEADERS, data={}, description="OCP Sync from Notion")
    make_request("POST", f"{ocp_prefix}/debug-sync-from-notion", headers=NO_AUTH_HEADERS, data={}, description="OCP Debug Sync from Notion")
    make_request("GET", f"{ocp_prefix}/diagnose-unknown-officers", headers=NO_AUTH_HEADERS, description="OCP Diagnose Unknown Officers (GET)")
    make_request("POST", f"{ocp_prefix}/diagnose-unknown-officers", headers=NO_AUTH_HEADERS, data={}, description="OCP Diagnose Unknown Officers (POST)")
    make_request("GET", f"{ocp_prefix}/officers", headers=NO_AUTH_HEADERS, description="OCP Get Officer Leaderboard")
    
    test_officer_email = "testofficer@example.com" # Use an email that might exist or not for testing
    make_request("GET", f"{ocp_prefix}/officer/{test_officer_email}/contributions", headers=NO_AUTH_HEADERS, description="OCP Get Officer Contributions")

    add_contrib_data = {"email": test_officer_email, "name": "Test Officer OCP", "event": "OCP Event", "points": 2, "role": "Participant"}
    make_request("POST", f"{ocp_prefix}/add-contribution", headers=NO_AUTH_HEADERS, data=add_contrib_data, description="OCP Add Contribution")
    
    # For update/delete, you'd need a valid point_id from a previously created contribution
    test_point_id = 1 # Replace with a real ID from your DB after an add
    update_contrib_data = {"points": 3, "event": "Updated OCP Event"}
    make_request("PUT", f"{ocp_prefix}/contribution/{test_point_id}", headers=NO_AUTH_HEADERS, data=update_contrib_data, description=f"OCP Update Contribution ID {test_point_id} (ensure ID exists)")
    make_request("DELETE", f"{ocp_prefix}/contribution/{test_point_id}", headers=NO_AUTH_HEADERS, description=f"OCP Delete Contribution ID {test_point_id} (ensure ID exists)")

    test_officer_id_ocp = "some_officer_uuid_or_email" # Use a valid identifier for an officer
    make_request("GET", f"{ocp_prefix}/officer/{test_officer_id_ocp}", headers=NO_AUTH_HEADERS, description="OCP Get Officer Details")
    make_request("GET", f"{ocp_prefix}/events", headers=NO_AUTH_HEADERS, description="OCP Get All Contribution Events")
    make_request("POST", f"{ocp_prefix}/repair-unknown-officers", headers=NO_AUTH_HEADERS, data={}, description="OCP Repair Unknown Officers")


def test_summarizer_endpoints():
    print("\n========== Testing Summarizer Endpoints ==========")
    make_request("GET", "/summarizer/status", headers=DEFAULT_HEADERS, description="Summarizer Status")
    make_request("GET", "/summarizer/config", headers=DEFAULT_HEADERS, description="Summarizer Get Config")
    
    config_data = {"model_name": "gemini-pro-test", "temperature": 0.8}
    make_request("POST", "/summarizer/config", headers=DEFAULT_HEADERS, data=config_data, description="Summarizer Update Config")
    
    gemini_test_data = {"text": "This is a test sentence for Gemini."}
    make_request("POST", "/summarizer/gemini/test", headers=DEFAULT_HEADERS, data=gemini_test_data, description="Summarizer Test Gemini Connection")


def test_users_endpoints():
    print("\n========== Testing Users Endpoints ==========")
    make_request("GET", "/users/", headers=NO_AUTH_HEADERS, description="Users Index") # Auth not specified, assuming public or adjust

    # Using the email from points test for consistency, assuming it was created
    existing_user_email = f"testuser_{int(time.time())-50}@example.com" # Approx email from points test
    # You might need to ensure this user exists or use a known one
    # For /viewUser, use the email of the user created in points section for better chance of success
    created_user_email_from_points = [d["email"] for d in created_users_for_points if "email" in d] # Helper to get it
    if created_user_email_from_points:
        existing_user_email = created_user_email_from_points[0]
        make_request("GET", "/users/viewUser", headers=DEFAULT_HEADERS, params={"user_identifier": existing_user_email}, description="Users View User by Email")
    else:
        print(f"Skipping /users/viewUser with specific email as no user was tracked from points creation.")
    make_request("GET", "/users/viewUser", headers=DEFAULT_HEADERS, params={"user_identifier": "nonexistent_user@example.com"}, description="Users View User - Non-existent (expect error)")
    
    # Create user (Note: backend expects query params for POST /createUser based on api.py)
    new_user_email_users = f"newuser_{int(time.time())}@example.com"
    create_user_params = {"email": new_user_email_users, "name": "New API User", "asu_id": "0987654321", "academic_standing": "Freshman", "major": "AI"}
    make_request("POST", "/users/createUser", headers=DEFAULT_HEADERS, params=create_user_params, description="Users Create User (via query params)")

    # GET /user
    make_request("GET", "/users/user", headers=DEFAULT_HEADERS, params={"email": new_user_email_users}, description="Users Get User by Email (created via /createUser)")
    
    # POST /user (Update existing or create if not found)
    update_user_data = {"email": new_user_email_users, "name": "Updated API User", "major": "Robotics"}
    make_request("POST", "/users/user", headers=DEFAULT_HEADERS, data=update_user_data, description="Users Update User (POST to /user)")
    
    new_user_for_post_upsert = f"upsert_{int(time.time())}@example.com"
    create_via_post_data = {"email": new_user_for_post_upsert, "name": "Upsert User", "asu_id": "112233", "academic_standing": "PHD", "major": "Space"}
    make_request("POST", "/users/user", headers=DEFAULT_HEADERS, data=create_via_post_data, description="Users Create User via POST to /user (Upsert)")

    # /submit-form
    form_data = {"discordID": "TestDiscord123", "role": "Tester"}
    make_request("POST", "/users/submit-form", headers=NO_AUTH_HEADERS, data=form_data, description="Users Submit Form")

# --- Main Execution ---
if __name__ == "__main__":
    start_time = time.time()
    if TEST_TOKEN == "YOUR_VALID_TEST_TOKEN":
        print("!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!")
        print("!!! WARNING: TEST_TOKEN is not set. Authenticated endpoints will likely fail. !!!")
        print("!!! Please replace 'YOUR_VALID_TEST_TOKEN' in the script with a valid token.  !!!")
        print("!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!\n")

    created_users_for_points = [] # Helper to pass created user email

    # Example of how to store created user info if needed by other tests
    # This is a simplified way; a proper test setup might use fixtures or a shared context.
    # For now, just running tests sequentially.

    test_auth_endpoints()
    test_points_endpoints() # This function now uses a dynamic email
    test_public_endpoints()
    test_calendar_endpoints()
    test_summarizer_endpoints()
    test_users_endpoints() # This function can try to use email from points test

    end_time = time.time()
    print(f"\n--- Test Execution Finished in {end_time - start_time:.2f} seconds ---")

    print("\n========== Test Summary ==========")
    total_tests = passed_tests + failed_tests
    print(f"Total tests attempted: {total_tests}")
    print(f"Passed tests: {passed_tests}")
    print(f"Failed tests: {failed_tests}")
    print("===============================")

    if failed_test_details:
        print("\n========== Failed Test Cases Details ==========")
        # Determine column widths
        desc_width = max(len("Test Description"), max(len(f['description']) for f in failed_test_details) if failed_test_details else 0) + 2
        method_width = max(len("Method"), max(len(f['method']) for f in failed_test_details) if failed_test_details else 0) + 2
        # url_width = max(len("URL"), max(len(f['url']) for f in failed_test_details) if failed_test_details else 0) + 2 # URL can be very long
        status_width = max(len("Status"), 6) + 2
        preview_width = max(len("Response Preview"), 50) + 2 # Fixed width for preview for now

        header = f"| {'Test Description':<{desc_width}} | {'Method':<{method_width}} | {'Status':<{status_width}} | {'Response Preview':<{preview_width}} | URL"
        print(header)
        print("|-" + "-" * desc_width + "-+- " + "-" * method_width + "-+- " + "-" * status_width + "-+- " + "-" * preview_width + "-|-----")

        for f_test in failed_test_details:
            status_str = str(f_test['status_code']) if f_test['status_code'] is not None else "N/A"
            # Truncate long descriptions/previews if necessary for table, actual data is in failed_test_details list
            desc_display = (f_test['description'][:desc_width-3] + "...") if len(f_test['description']) > desc_width-1 else f_test['description']
            preview_display = (f_test['response_preview'][:preview_width-3] + "...") if len(f_test['response_preview']) > preview_width-1 else f_test['response_preview']
            
            print(f"| {desc_display:<{desc_width}} | {f_test['method']:<{method_width}} | {status_str:<{status_width}} | {preview_display:<{preview_width}} | {f_test['url']}")
        print("=============================================")

    print("\nReview the output above for detailed status codes and responses for each test.")
    print("A FAILED status indicates either a request exception or an assertion failure based on expected status codes.") 