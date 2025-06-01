import React, { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import apiClient from '../components/utils/axios';
import useAuthToken from '../hooks/userAuth';
import Orb from '../components/ui/Orb';
import { Menu, MenuItem, HoveredLink } from '../components/ui/navbar-menu';
import { FileUpload } from '../components/ui/file-upload';
import StarBorder from '../components/ui/StarBorder';
import { FaFileUpload, FaUserPlus, FaSignOutAlt, FaTachometerAlt, FaUsers, FaClipboardList } from 'react-icons/fa';

const HomePage = () => {
  useAuthToken();
  const navigate = useNavigate();

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
    const formData = new FormData();
    formData.append('file', eventFile);
    formData.append('event_name', eventName);
    formData.append('event_points', eventPoints);
    try {
      const response = await apiClient.post('points/uploadEventCSV', formData);
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
      const response = await apiClient.post('points/assignPoints', data);
      alert(response.data.message || 'Points assigned successfully!');
      setUserIdentifier(''); setUserPoints(''); setEvent(''); setAwardedByOfficer('');
    } catch (error) {
      alert(error.response?.data?.error || 'Error assigning points.');
    }
  };

  const handleLogout = () => {
    localStorage.removeItem('accessToken');
    localStorage.removeItem('refreshToken');
    navigate('/');
  };

  const navItems = [
    { name: "Dashboard", link: "/home", icon: <FaTachometerAlt className="h-4 w-4 md:mr-2" /> },
    { name: "User Management", link: "/users", icon: <FaUsers className="h-4 w-4 md:mr-2" /> },
    { name: "Leaderboard", link: "/leaderboard", icon: <FaClipboardList className="h-4 w-4 md:mr-2" /> },
  ];

  return (
    <div className="relative min-h-screen bg-soda-black text-soda-white overflow-x-hidden pt-20">
      <div className="fixed inset-0 z-0">
        <Orb hue={260} forceHoverState={true} hoverIntensity={0.05} />
        <div className="absolute inset-0 bg-soda-black/60 backdrop-blur-lg z-1"></div>
      </div>

      <Menu setActive={setActiveNavItem}>
        {navItems.map((item) => (
          <MenuItem setActive={setActiveNavItem} active={activeNavItem} item={item.name} key={item.name}>
            <HoveredLink href={item.link}>
              <div className="flex items-center">
                {item.icon}
                <span className="hidden md:inline">{item.name}</span>
              </div>
            </HoveredLink>
          </MenuItem>
        ))}
        <MenuItem setActive={setActiveNavItem} active={activeNavItem} item="Account">
          <div className="flex flex-col space-y-2 text-sm p-2">
            <HoveredLink href="#" onClick={handleLogout}>
              <div className="flex items-center">
                <FaSignOutAlt className="h-4 w-4 mr-2" />
                Logout
              </div>
            </HoveredLink>
          </div>
        </MenuItem>
      </Menu>

      <div className="relative z-20 container mx-auto px-4 py-12 md:py-16 flex flex-col lg:flex-row lg:space-x-8 space-y-8 lg:space-y-0 items-start justify-center">
        <div className="bg-soda-gray/70 backdrop-blur-xl p-6 md:p-8 rounded-xl shadow-2xl w-full max-w-lg">
          <h2 className="text-2xl md:text-3xl font-bold mb-6 text-soda-white text-center flex items-center justify-center">
            <FaFileUpload className="mr-3 h-7 w-7 text-soda-blue" /> Upload Event CSV
          </h2>
          <form onSubmit={handleFileUploadSubmit} className="space-y-6">
            <div>
              <label htmlFor="eventNameCsv" className="block text-sm font-medium text-soda-white mb-1">Event Name</label>
              <input
                id="eventNameCsv"
                type="text"
                className="w-full p-3 rounded-md bg-soda-black/50 border border-soda-white/20 text-soda-white focus:ring-soda-blue focus:border-soda-blue transition-all"
                value={eventName}
                onChange={(e) => setEventName(e.target.value)}
                required
              />
            </div>
            <div>
              <label htmlFor="eventPointsCsv" className="block text-sm font-medium text-soda-white mb-1">Event Points</label>
              <input
                id="eventPointsCsv"
                type="number"
                className="w-full p-3 rounded-md bg-soda-black/50 border border-soda-white/20 text-soda-white focus:ring-soda-blue focus:border-soda-blue transition-all"
                value={eventPoints}
                onChange={(e) => setEventPoints(e.target.value)}
                required
              />
            </div>
            <FileUpload onChange={(files) => setEventFile(files[0])} />
            <StarBorder type="submit" color="#007AFF" speed="4s" className="w-full">
              Upload CSV
            </StarBorder>
          </form>
        </div>

        <div className="bg-soda-gray/70 backdrop-blur-xl p-6 md:p-8 rounded-xl shadow-2xl w-full max-w-lg">
          <h2 className="text-2xl md:text-3xl font-bold mb-6 text-soda-white text-center flex items-center justify-center">
            <FaUserPlus className="mr-3 h-7 w-7 text-soda-red" /> Assign Points Manually
          </h2>
          <form onSubmit={handleAssignPointsSubmit} className="space-y-6">
            <div>
              <label htmlFor="userIdentifier" className="block text-sm font-medium text-soda-white mb-1">User Identifier (Email/UUID)</label>
              <input
                id="userIdentifier"
                type="text"
                className="w-full p-3 rounded-md bg-soda-black/50 border border-soda-white/20 text-soda-white focus:ring-soda-blue focus:border-soda-blue transition-all"
                value={userIdentifier}
                onChange={(e) => setUserIdentifier(e.target.value)}
                required
              />
            </div>
            <div>
              <label htmlFor="userPoints" className="block text-sm font-medium text-soda-white mb-1">Points</label>
              <input
                id="userPoints"
                type="number"
                className="w-full p-3 rounded-md bg-soda-black/50 border border-soda-white/20 text-soda-white focus:ring-soda-blue focus:border-soda-blue transition-all"
                value={userPoints}
                onChange={(e) => setUserPoints(e.target.value)}
                required
              />
            </div>
            <div>
              <label htmlFor="eventManual" className="block text-sm font-medium text-soda-white mb-1">Event</label>
              <input
                id="eventManual"
                type="text"
                className="w-full p-3 rounded-md bg-soda-black/50 border border-soda-white/20 text-soda-white focus:ring-soda-blue focus:border-soda-blue transition-all"
                value={event}
                onChange={(e) => setEvent(e.target.value)}
                required
              />
            </div>
            <div>
              <label htmlFor="awardedBy" className="block text-sm font-medium text-soda-white mb-1">Awarded by Officer</label>
              <input
                id="awardedBy"
                type="text"
                className="w-full p-3 rounded-md bg-soda-black/50 border border-soda-white/20 text-soda-white focus:ring-soda-blue focus:border-soda-blue transition-all"
                value={awardedByOfficer}
                onChange={(e) => setAwardedByOfficer(e.target.value)}
                required
              />
            </div>
            <StarBorder type="submit" color="#FF3B30" speed="4s" className="w-full">
              Assign Points
            </StarBorder>
          </form>
        </div>
      </div>
    </div>
  );
};

export default HomePage;
