import React, { useState } from 'react';
import apiClient from '../components/utils/axios';
import useAuthToken from '../hooks/userAuth';
import useOrgNavigation from '../hooks/useOrgNavigation';
import { useAuth } from '../components/auth/AuthContext';
import OrganizationNavbar from '../components/shared/OrganizationNavbar';
import { FileUpload } from '../components/ui/file-upload';
import StarBorder from '../components/ui/StarBorder';
import { 
  FaFileUpload, 
  FaUserPlus, 
  FaSignOutAlt, 
  FaTachometerAlt, 
  FaUsers, 
  FaClipboardList, 
  FaCogs,
  FaChartLine,
  FaArrowLeft
} from 'react-icons/fa';

const AddPoints = () => {
  useAuthToken();
  const { currentOrg } = useAuth();
  const { 
    goToDashboard,
    goToUsers, 
    goToLeaderboard,
    goToOCP,
    goToPanel,
    goToJeopardy 
  } = useOrgNavigation();

  const [eventFile, setEventFile] = useState(null);
  const [eventName, setEventName] = useState('');
  const [eventPoints, setEventPoints] = useState('');
  const [userIdentifier, setUserIdentifier] = useState('');
  const [userPoints, setUserPoints] = useState('');
  const [event, setEvent] = useState('');
  const [awardedByOfficer, setAwardedByOfficer] = useState('');

  const handleFileUploadSubmit = async (e) => {
    e.preventDefault();
    if (!eventFile || !eventName || !eventPoints) {
      alert('Please fill all fields and select a file for event CSV upload.');
      return;
    }
    
    // FileUpload component passes an array, so get the first file
    const fileToUpload = Array.isArray(eventFile) ? eventFile[0] : eventFile;
    
    if (!fileToUpload) {
      alert('Please select a file to upload.');
      return;
    }
    
    const formData = new FormData();
    formData.append('file', fileToUpload);
    formData.append('event_name', eventName);
    formData.append('event_points', eventPoints);
    try {
      const response = await apiClient.post('/api/points/uploadEventCSV', formData);
      alert(response.data.message || 'File uploaded successfully!');
      setEventFile(null); setEventName(''); setEventPoints('');
    } catch (error) {
      alert(error.response?.data?.error || 'Error uploading file.');
    }
  };

  const handleAssignPointsSubmit = async (e) => {
    e.preventDefault();
    if (!userIdentifier || !userPoints || !event || !awardedByOfficer) {
      alert('Please fill all fields for assigning points.');
      return;
    }
    const data = { user_identifier: userIdentifier, points: userPoints, event, awarded_by_officer: awardedByOfficer };
    try {
      const response = await apiClient.post('/api/points/assign_points', data);
      alert(response.data.message || 'Points assigned successfully!');
      setUserIdentifier(''); setUserPoints(''); setEvent(''); setAwardedByOfficer('');
    } catch (error) {
      alert(error.response?.data?.error || 'Error assigning points.');
    }
  };

  return (
    <OrganizationNavbar>
      <div className="max-w-7xl mx-auto">
        <div className="text-center mt-20 mb-10">
          <h1 className="text-3xl font-bold mb-2">Add Points</h1>
          <p className="text-gray-400">Award points to users for events and activities</p>
        </div>

        <div className="grid grid-cols-1 lg:grid-cols-2 gap-8">
          {/* Section 1: Upload Event CSV */}
          <div className="bg-gray-900/50 backdrop-blur-sm rounded-xl border border-gray-700 p-6">
            <h2 className="text-xl font-semibold mb-4 flex items-center">
              <FaFileUpload className="mr-2 text-blue-400" />
              Upload Event CSV
            </h2>
            
            <form onSubmit={handleFileUploadSubmit} className="space-y-4">
              <div>
                <label className="block text-sm font-medium text-gray-300 mb-1">Event Name</label>
                <input
                  type="text"
                  value={eventName}
                  onChange={(e) => setEventName(e.target.value)}
                  placeholder="e.g., Spring Workshop 2024"
                  className="w-full px-3 py-2 bg-gray-800 border border-gray-600 rounded-md text-white placeholder-gray-400 focus:outline-none focus:border-blue-500"
                  required
                />
              </div>

              <div>
                <label className="block text-sm font-medium text-gray-300 mb-1">Points per Participant</label>
                <input
                  type="number"
                  value={eventPoints}
                  onChange={(e) => setEventPoints(e.target.value)}
                  placeholder="10"
                  className="w-full px-3 py-2 bg-gray-800 border border-gray-600 rounded-md text-white placeholder-gray-400 focus:outline-none focus:border-blue-500"
                  required
                />
              </div>

              <div>
                <label className="block text-sm font-medium text-gray-300 mb-1">CSV File</label>
                <FileUpload
                  value={eventFile}
                  onChange={setEventFile}
                  accept=".csv"
                  maxFiles={1}
                  className="w-full"
                />
                <p className="text-xs text-gray-400 mt-1">
                  Upload a CSV file with participant emails (one per line)
                </p>
              </div>

              <button
                type="submit"
                className="w-full px-4 py-2 bg-blue-600 hover:bg-blue-700 rounded-md text-white font-medium transition-colors"
              >
                Upload Event CSV
              </button>
            </form>
          </div>

          {/* Section 2: Assign Individual Points */}
          <div className="bg-gray-900/50 backdrop-blur-sm rounded-xl border border-gray-700 p-6">
            <h2 className="text-xl font-semibold mb-4 flex items-center">
              <FaUserPlus className="mr-2 text-green-400" />
              Assign Individual Points
            </h2>
            
            <form onSubmit={handleAssignPointsSubmit} className="space-y-4">
              <div>
                <label className="block text-sm font-medium text-gray-300 mb-1">User Email or ASU ID</label>
                <input
                  type="text"
                  value={userIdentifier}
                  onChange={(e) => setUserIdentifier(e.target.value)}
                  placeholder="user@example.com or 1234567890"
                  className="w-full px-3 py-2 bg-gray-800 border border-gray-600 rounded-md text-white placeholder-gray-400 focus:outline-none focus:border-green-500"
                  required
                />
              </div>

              <div>
                <label className="block text-sm font-medium text-gray-300 mb-1">Points to Award</label>
                <input
                  type="number"
                  value={userPoints}
                  onChange={(e) => setUserPoints(e.target.value)}
                  placeholder="5"
                  className="w-full px-3 py-2 bg-gray-800 border border-gray-600 rounded-md text-white placeholder-gray-400 focus:outline-none focus:border-green-500"
                  required
                />
              </div>

              <div>
                <label className="block text-sm font-medium text-gray-300 mb-1">Event/Reason</label>
                <input
                  type="text"
                  value={event}
                  onChange={(e) => setEvent(e.target.value)}
                  placeholder="e.g., Workshop Participation"
                  className="w-full px-3 py-2 bg-gray-800 border border-gray-600 rounded-md text-white placeholder-gray-400 focus:outline-none focus:border-green-500"
                  required
                />
              </div>

              <div>
                <label className="block text-sm font-medium text-gray-300 mb-1">Awarded By Officer</label>
                <input
                  type="text"
                  value={awardedByOfficer}
                  onChange={(e) => setAwardedByOfficer(e.target.value)}
                  placeholder="Officer Name"
                  className="w-full px-3 py-2 bg-gray-800 border border-gray-600 rounded-md text-white placeholder-gray-400 focus:outline-none focus:border-green-500"
                  required
                />
              </div>

              <button
                type="submit"
                className="w-full px-4 py-2 bg-green-600 hover:bg-green-700 rounded-md text-white font-medium transition-colors"
              >
                Assign Points
              </button>
            </form>
          </div>
        </div>

        {/* Instructions Section */}
        <div className="mt-8 bg-gray-900/50 backdrop-blur-sm rounded-xl border border-gray-700 p-6">
          <h3 className="text-lg font-semibold mb-4 text-white">Instructions</h3>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-6 text-sm text-gray-300">
            <div>
              <h4 className="font-medium text-blue-400 mb-2">Event CSV Upload</h4>
              <ul className="space-y-1">
                <li>• Create a CSV file with participant emails (one per line)</li>
                <li>• Specify the event name and points per participant</li>
                <li>• All participants will receive the same number of points</li>
                <li>• Perfect for workshops, meetings, and group events</li>
              </ul>
            </div>
            <div>
              <h4 className="font-medium text-green-400 mb-2">Individual Points</h4>
              <ul className="space-y-1">
                <li>• Award points to specific users by email or ASU ID</li>
                <li>• Specify the reason and awarding officer</li>
                <li>• Great for individual achievements and special cases</li>
                <li>• Points are immediately added to the user's total</li>
              </ul>
            </div>
          </div>
        </div>
      </div>
    </OrganizationNavbar>
  );
};

export default AddPoints;