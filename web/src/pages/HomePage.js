import React, { useState} from 'react';
import { useNavigate } from 'react-router-dom';
import Sidebar from '../components/SideBar';  // Re-add the Sidebar
import apiClient from '../components/utils/axios';
import useAuthToken from '../hooks/userAuth';

const HomePage = () => {
  useAuthToken();
  const [eventFile, setEventFile] = useState(null);
  const [eventName, setEventName] = useState('');
  const [eventPoints, setEventPoints] = useState('');
  const [userIdentifier, setUserIdentifier] = useState('');
  const [userPoints, setUserPoints] = useState('');
  const [event, setEvent] = useState('');
  const [awardedByOfficer, setAwardedByOfficer] = useState('');
  const [isSidebarOpen, setIsSidebarOpen] = useState(false);
  const navigate = useNavigate();

  // Handle file upload form submission
  const handleFileUpload = async (e) => {
    e.preventDefault();
  
    if (!eventFile || !eventName || !eventPoints) {
      alert('Please fill all fields');
      return;
    }
  
    const formData = new FormData();
    formData.append('file', eventFile);
    formData.append('event_name', eventName);
    formData.append('event_points', eventPoints);
  
    try {
      const response = await apiClient.post('points/uploadEventCSV', formData);
      if (response.data) {
        alert(response.data.message);  // Handle success case
      }
    } catch (error) {
      // Handle error case
      if (error.response && error.response.data && error.response.data.error) {
        alert(`Error: ${error.response.data.error}`);  // Error message from backend
      } else {
        alert('An error occurred while uploading the file.');
      }
    }
  };
  

 
  


  // Handle manual points assignment form submission
  const handleAssignPoints = async (e) => {
    e.preventDefault();
  
    if (!userIdentifier || !userPoints || !event || !awardedByOfficer) {
      alert('Please fill all fields');
      return;
    }
  
    const data = {
      user_identifier: userIdentifier,
      points: userPoints,
      event,
      awarded_by_officer: awardedByOfficer,
    };
  
    try {
      const response = await apiClient.post('points/assignPoints', data);
  
      // Ensure we have a response before accessing response.data
      if (response && response.data) {
        alert(response.data.message); // Handle success case
      } else {
        alert('Unexpected response from the server.');
      }
    } catch (error) {
      // Handle error case
      if (error.response && error.response.data && error.response.data.error) {
        alert(`Error: ${error.response.data.error}`); // Backend error message
      } else {
        alert('An error occurred while assigning points.');
      }
    }
  };
  
  return (
    <div className="min-h-screen flex bg-gray-900 text-white">
      {/* Sidebar */}
      

      {/* Main Content */}
      <div className={`flex-1 p-8 ${isSidebarOpen ? 'ml-60' : 'ml-16'}`}>
        <h1 className="text-4xl font-bold mb-8 text-center" style={{ color: '#ba3554' }}>SoDA Home</h1>

        {/* Upload Event CSV Form */}
        <div className="bg-gray-800 p-6 rounded-lg shadow-lg w-full max-w-lg mx-auto mb-8">
          <h2 className="text-2xl font-bold mb-4">Upload Event CSV</h2>
          <form onSubmit={handleFileUpload}>
            <div className="mb-4">
              <label className="block text-white mb-2">Event Name</label>
              <input
                type="text"
                className="w-full p-2 rounded-md bg-gray-700 text-white"
                value={eventName}
                onChange={(e) => setEventName(e.target.value)}
                required
              />
            </div>

            <div className="mb-4">
              <label className="block text-white mb-2">Event Points</label>
              <input
                type="number"
                className="w-full p-2 rounded-md bg-gray-700 text-white"
                value={eventPoints}
                onChange={(e) => setEventPoints(e.target.value)}
                required
              />
            </div>

            <div className="mb-4">
              <label className="block text-white mb-2">Upload CSV File</label>
              <input
                type="file"
                className="w-full p-2 rounded-md bg-gray-700 text-white"
                accept=".csv"
                onChange={(e) => setEventFile(e.target.files[0])}
                required
              />
            </div>

            <button
              type="submit"
              className="w-full py-2 px-4 bg-blue-600 hover:bg-blue-700 rounded-md text-white font-semibold"
            >
              Upload CSV
            </button>
          </form>
        </div>

        {/* Assign Points Form */}
        <div className="bg-gray-800 p-6 rounded-lg shadow-lg w-full max-w-lg mx-auto">
          <h2 className="text-2xl font-bold mb-4">Assign Points</h2>
          <form onSubmit={handleAssignPoints}>
            <div className="mb-4">
              <label className="block text-white mb-2">User Identifier (Email/UUID)</label>
              <input
                type="text"
                className="w-full p-2 rounded-md bg-gray-700 text-white"
                value={userIdentifier}
                onChange={(e) => setUserIdentifier(e.target.value)}
                required
              />
            </div>

            <div className="mb-4">
              <label className="block text-white mb-2">Points</label>
              <input
                type="number"
                className="w-full p-2 rounded-md bg-gray-700 text-white"
                value={userPoints}
                onChange={(e) => setUserPoints(e.target.value)}
                required
              />
            </div>

            <div className="mb-4">
              <label className="block text-white mb-2">Event</label>
              <input
                type="text"
                className="w-full p-2 rounded-md bg-gray-700 text-white"
                value={event}
                onChange={(e) => setEvent(e.target.value)}
                required
              />
            </div>

            <div className="mb-4">
              <label className="block text-white mb-2">Awarded by Officer</label>
              <input
                type="text"
                className="w-full p-2 rounded-md bg-gray-700 text-white"
                value={awardedByOfficer}
                onChange={(e) => setAwardedByOfficer(e.target.value)}
                required
              />
            </div>

            <button
              type="submit"
              className="w-full py-2 px-4"
              style={{ backgroundColor: '#4462dc' }}
            >
              Assign Points
            </button>
          </form>
        </div>
      </div>
      <Sidebar isSidebarOpen={isSidebarOpen} toggleSidebar={() => setIsSidebarOpen(!isSidebarOpen)} />
    </div>
  );
};

export default HomePage;
