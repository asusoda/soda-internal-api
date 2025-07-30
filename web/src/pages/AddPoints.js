import React, { useState } from 'react';
import apiClient from '../components/utils/axios';
import useAuthToken from '../hooks/userAuth';
import useOrgNavigation from '../hooks/useOrgNavigation';
import { useAuth } from '../components/auth/AuthContext';
import Orb from '../components/ui/Orb';
import { Menu, MenuItem, HoveredLink } from '../components/ui/navbar-menu';
import { FileUpload } from '../components/ui/file-upload';
import StarBorder from '../components/ui/StarBorder';
import OrganizationSwitcher from '../components/OrganizationSwitcher';
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
  const { logout, currentOrg } = useAuth();
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
  const [activeNavItem, setActiveNavItem] = useState(null);

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
    <div className="relative min-h-screen bg-black text-white overflow-hidden">
      {/* Background Effects */}
      <div className="absolute inset-0">
        <Orb />
      </div>

      {/* Navigation */}
      <div className="relative z-20 w-full">
        <Menu setActive={setActiveNavItem}>
          <div className="flex items-center justify-between w-full px-4 py-4">
            {/* Left side - Organization info */}
            <div className="flex items-center space-x-4">
              {currentOrg && (
                <div className="flex items-center space-x-2">
                  {currentOrg.icon_url && (
                    <img 
                      src={currentOrg.icon_url} 
                      alt={currentOrg.name}
                      className="w-8 h-8 rounded-full"
                    />
                  )}
                  <div>
                    <h1 className="text-xl font-bold">{currentOrg.name} - Add Points</h1>
                    <p className="text-sm text-gray-400">/{currentOrg.prefix}/addpoints</p>
                  </div>
                </div>
              )}
            </div>

            {/* Center - Navigation Menu */}
            <div className="flex items-center space-x-6">
              <MenuItem setActive={setActiveNavItem} active={activeNavItem} item="Navigation">
                <div className="flex flex-col space-y-4 text-sm">
                  <HoveredLink onClick={goToDashboard}>
                    <FaTachometerAlt className="inline mr-2" />Dashboard
                  </HoveredLink>
                  <HoveredLink onClick={goToUsers}>
                    <FaUsers className="inline mr-2" />User Management
                  </HoveredLink>
                  <HoveredLink onClick={goToLeaderboard}>
                    <FaChartLine className="inline mr-2" />Leaderboard
                  </HoveredLink>
                  <HoveredLink onClick={goToOCP}>
                    <FaClipboardList className="inline mr-2" />OCP Details
                  </HoveredLink>
                </div>
              </MenuItem>

              <MenuItem setActive={setActiveNavItem} active={activeNavItem} item="Games">
                <div className="flex flex-col space-y-4 text-sm">
                  <HoveredLink onClick={goToJeopardy}>
                    <FaTachometerAlt className="inline mr-2" />Jeopardy
                  </HoveredLink>
                  <HoveredLink onClick={goToPanel}>
                    <FaCogs className="inline mr-2" />Bot Panel
                  </HoveredLink>
                </div>
              </MenuItem>
            </div>

            {/* Right side - Organization switcher and logout */}
            <div className="flex items-center space-x-4">
              <OrganizationSwitcher />
              <button 
                onClick={logout}
                className="flex items-center space-x-2 px-3 py-2 rounded-md text-sm font-medium text-gray-300 hover:text-white hover:bg-gray-700 transition-colors"
              >
                <FaSignOutAlt />
                <span>Logout</span>
              </button>
            </div>
          </div>
        </Menu>
      </div>

      {/* Main Content */}
      <div className="relative z-10 px-4 py-8">
        <div className="max-w-6xl mx-auto">
          {/* Back to Dashboard Button */}
          <button
            onClick={goToDashboard}
            className="flex items-center space-x-2 text-gray-400 hover:text-white transition-colors mb-8"
          >
            <FaArrowLeft />
            <span>Back to Dashboard</span>
          </button>

          {/* Page Header */}
          <div className="text-center mb-12">
            <h1 className="text-4xl md:text-5xl font-bold mb-4">
              Add Points
            </h1>
            <p className="text-xl text-gray-400 max-w-2xl mx-auto">
              Award points to users through CSV upload or individual assignment
            </p>
          </div>

          {/* Content Grid */}
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-8">
            
            {/* Event CSV Upload */}
            <div className="relative">
              <StarBorder>
                <div className="p-8 bg-gray-900/50 backdrop-blur-sm rounded-lg border border-gray-700">
                  <div className="flex items-center mb-6">
                    <div className="p-3 rounded-lg bg-gradient-to-br from-blue-500 to-blue-600 text-white mr-4">
                      <FaFileUpload className="w-6 h-6" />
                    </div>
                    <div>
                      <h2 className="text-2xl font-bold">Upload Event CSV</h2>
                      <p className="text-gray-400">Bulk import points from a CSV file</p>
                    </div>
                  </div>
                  
                  <form onSubmit={handleFileUploadSubmit} className="space-y-4">
                    <input
                      type="text"
                      placeholder="Event Name"
                      value={eventName}
                      onChange={(e) => setEventName(e.target.value)}
                      className="w-full p-3 bg-gray-800 border border-gray-600 rounded-lg text-white placeholder-gray-400 focus:border-blue-500 focus:outline-none transition-colors"
                    />
                    <input
                      type="number"
                      placeholder="Event Points"
                      value={eventPoints}
                      onChange={(e) => setEventPoints(e.target.value)}
                      className="w-full p-3 bg-gray-800 border border-gray-600 rounded-lg text-white placeholder-gray-400 focus:border-blue-500 focus:outline-none transition-colors"
                    />
                    <FileUpload onChange={setEventFile} />
                    <button
                      type="submit"
                      className="w-full bg-gradient-to-r from-blue-500 to-blue-600 hover:from-blue-600 hover:to-blue-700 text-white font-bold py-3 px-6 rounded-lg transition-all duration-200 flex items-center justify-center space-x-2 transform hover:scale-105"
                    >
                      <FaFileUpload />
                      <span>Upload CSV</span>
                    </button>
                  </form>
                </div>
              </StarBorder>
            </div>

            {/* Manual Points Assignment */}
            <div className="relative">
              <StarBorder>
                <div className="p-8 bg-gray-900/50 backdrop-blur-sm rounded-lg border border-gray-700">
                  <div className="flex items-center mb-6">
                    <div className="p-3 rounded-lg bg-gradient-to-br from-purple-500 to-purple-600 text-white mr-4">
                      <FaUserPlus className="w-6 h-6" />
                    </div>
                    <div>
                      <h2 className="text-2xl font-bold">Assign Points Manually</h2>
                      <p className="text-gray-400">Award points to individual users</p>
                    </div>
                  </div>
                  
                  <form onSubmit={handleAssignPointsSubmit} className="space-y-4">
                    <input
                      type="text"
                      placeholder="User Identifier (email or username)"
                      value={userIdentifier}
                      onChange={(e) => setUserIdentifier(e.target.value)}
                      className="w-full p-3 bg-gray-800 border border-gray-600 rounded-lg text-white placeholder-gray-400 focus:border-purple-500 focus:outline-none transition-colors"
                    />
                    <input
                      type="number"
                      placeholder="Points"
                      value={userPoints}
                      onChange={(e) => setUserPoints(e.target.value)}
                      className="w-full p-3 bg-gray-800 border border-gray-600 rounded-lg text-white placeholder-gray-400 focus:border-purple-500 focus:outline-none transition-colors"
                    />
                    <input
                      type="text"
                      placeholder="Event Name"
                      value={event}
                      onChange={(e) => setEvent(e.target.value)}
                      className="w-full p-3 bg-gray-800 border border-gray-600 rounded-lg text-white placeholder-gray-400 focus:border-purple-500 focus:outline-none transition-colors"
                    />
                    <input
                      type="text"
                      placeholder="Awarded by Officer"
                      value={awardedByOfficer}
                      onChange={(e) => setAwardedByOfficer(e.target.value)}
                      className="w-full p-3 bg-gray-800 border border-gray-600 rounded-lg text-white placeholder-gray-400 focus:border-purple-500 focus:outline-none transition-colors"
                    />
                    <button
                      type="submit"
                      className="w-full bg-gradient-to-r from-purple-500 to-purple-600 hover:from-purple-600 hover:to-purple-700 text-white font-bold py-3 px-6 rounded-lg transition-all duration-200 flex items-center justify-center space-x-2 transform hover:scale-105"
                    >
                      <FaUserPlus />
                      <span>Assign Points</span>
                    </button>
                  </form>
                </div>
              </StarBorder>
            </div>
          </div>

          {/* Help Section */}
          <div className="mt-12">
            <div className="bg-gray-900/30 backdrop-blur-sm rounded-lg border border-gray-700 p-6">
              <h3 className="text-lg font-semibold mb-4">📋 How to Use</h3>
              <div className="grid grid-cols-1 md:grid-cols-2 gap-6 text-sm text-gray-400">
                <div>
                  <h4 className="font-semibold text-white mb-2">CSV Upload:</h4>
                  <ul className="space-y-1">
                    <li>• Prepare a CSV file with user data</li>
                    <li>• Enter event name and point value</li>
                    <li>• Upload file to award points to all users</li>
                  </ul>
                </div>
                <div>
                  <h4 className="font-semibold text-white mb-2">Manual Assignment:</h4>
                  <ul className="space-y-1">
                    <li>• Enter user email or username</li>
                    <li>• Specify point amount and event</li>
                    <li>• Add your name as the awarding officer</li>
                  </ul>
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};

export default AddPoints;