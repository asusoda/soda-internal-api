import React, { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import apiClient from '../components/utils/axios';
import useAuthToken from '../hooks/userAuth';
import Orb from '../components/ui/Orb';
import { Menu, MenuItem, HoveredLink } from '../components/ui/navbar-menu';
import StarBorder from '../components/ui/StarBorder';
import { FaSearch, FaUserEdit, FaUserPlus, FaSignOutAlt, FaTachometerAlt, FaUsers, FaClipboardList } from 'react-icons/fa';

const UserPage = () => {
  useAuthToken();
  const navigate = useNavigate();

  // State for Navbar
  const [activeNavItem, setActiveNavItem] = useState("User Management");

  // State for Find/Update User
  const [searchEmail, setSearchEmail] = useState('');
  const [userData, setUserData] = useState(null);
  const [updateName, setUpdateName] = useState('');
  const [updateAsuId, setUpdateAsuId] = useState('');
  const [updateAcademicStanding, setUpdateAcademicStanding] = useState('');
  const [updateMajor, setUpdateMajor] = useState('');
  const [fetchError, setFetchError] = useState('');
  const [updateSuccessMessage, setUpdateSuccessMessage] = useState('');
  const [updateError, setUpdateError] = useState('');

  // State for Create User
  const [createEmail, setCreateEmail] = useState('');
  const [createName, setCreateName] = useState('');
  const [createAsuId, setCreateAsuId] = useState('');
  const [createAcademicStanding, setCreateAcademicStanding] = useState('');
  const [createMajor, setCreateMajor] = useState('');
  const [createSuccessMessage, setCreateSuccessMessage] = useState('');
  const [createError, setCreateError] = useState('');
  
  const [loading, setLoading] = useState(false);

  // Fetch User Logic
  const handleFetchUser = async () => {
    if (!searchEmail) {
      setFetchError('Please enter an email to search.');
      return;
    }
    setLoading(true);
    setFetchError('');
    setUpdateSuccessMessage('');
    setUpdateError('');
    setUserData(null);
    try {
      const response = await apiClient.get(`/users/user?email=${searchEmail}`);
      setUserData(response.data);
      setUpdateName(response.data.name || '');
      setUpdateAsuId(response.data.asu_id || '');
      setUpdateAcademicStanding(response.data.academic_standing || '');
      setUpdateMajor(response.data.major || '');
    } catch (error) {
      setUserData(null); // Clear previous user data on new error
      if (error.response && error.response.status === 404) {
        setFetchError('User not found. You can create a new user or try a different email.');
      } else {
        setFetchError(error.response?.data?.error || 'An error occurred while fetching the user.');
      }
    }
    setLoading(false);
  };

  // Update User Logic
  const handleUpdateUser = async (e) => {
    e.preventDefault();
    if (!userData || !userData.email) {
        setUpdateError('No user selected or user email is missing.');
        return;
    }
    setLoading(true);
    setUpdateError('');
    setUpdateSuccessMessage('');
    const dataToUpdate = {
      email: userData.email, // Use email from fetched userData
      name: updateName,
      asu_id: updateAsuId,
      academic_standing: updateAcademicStanding,
      major: updateMajor,
    };
    try {
      const response = await apiClient.post('/users/user', dataToUpdate);
      setUpdateSuccessMessage(response.data.message || 'User updated successfully!');
       // Optionally re-fetch user data or update UI directly
      setUserData(prev => ({...prev, ...dataToUpdate, email: prev.email})); // Keep original email, update other fields
    } catch (error) {
      setUpdateError(error.response?.data?.error || 'An error occurred while updating the user.');
    }
    setLoading(false);
  };

  // Create User Logic
  const handleCreateUser = async (e) => {
    e.preventDefault();
    if (!createEmail || !createName || !createAsuId || !createAcademicStanding || !createMajor) {
      setCreateError('All fields are required for creating a user.');
      return;
    }
    setLoading(true);
    setCreateError('');
    setCreateSuccessMessage('');
    const data = {
      email: createEmail,
      name: createName,
      asu_id: createAsuId,
      academic_standing: createAcademicStanding,
      major: createMajor,
    };
    try {
      const response = await apiClient.post('users/createUser', data);
      setCreateSuccessMessage(response.data.message || 'User created successfully!');
      setCreateEmail('');
      setCreateName('');
      setCreateAsuId('');
      setCreateAcademicStanding('');
      setCreateMajor('');
    } catch (error) {
      setCreateError(error.response?.data?.error || 'An error occurred while creating the user.');
    }
    setLoading(false);
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
        <Orb hue={220} forceHoverState={true} hoverIntensity={0.05} /> {/* Adjusted Hue for UserPage */}
        <div className="absolute inset-0 bg-soda-black/60 backdrop-blur-lg z-1"></div>
      </div>

      <Menu setActive={setActiveNavItem}>
        {navItems.map((item) => (
          <MenuItem setActive={setActiveNavItem} active={activeNavItem === item.name} item={item.name} key={item.name}>
            <HoveredLink href={item.link}>
              <div className="flex items-center">
                {item.icon}
                <span className="hidden md:inline">{item.name}</span>
              </div>
            </HoveredLink>
          </MenuItem>
        ))}
        <MenuItem setActive={setActiveNavItem} active={activeNavItem === "Account"} item="Account">
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

      <div className="relative z-20 container mx-auto px-4 py-12 md:py-16 flex flex-col items-center space-y-8">
        {/* Find User Section */}
        <div className="bg-soda-gray/70 backdrop-blur-xl p-6 md:p-8 rounded-xl shadow-2xl w-full max-w-xl">
          <h2 className="text-2xl md:text-3xl font-bold mb-6 text-soda-white text-center flex items-center justify-center">
            <FaSearch className="mr-3 h-7 w-7 text-soda-blue" /> Find User
          </h2>
          <div className="space-y-4">
            <input
              type="email"
              className="w-full p-3 rounded-md bg-soda-black/50 border border-soda-white/20 text-soda-white focus:ring-soda-blue focus:border-soda-blue transition-all"
              placeholder="Enter user email to find or update"
              value={searchEmail}
              onChange={(e) => setSearchEmail(e.target.value)}
            />
            <StarBorder onClick={handleFetchUser} disabled={loading} color="#007AFF" speed="4s" className="w-full">
              {loading && !userData ? 'Searching...' : 'Search User'}
            </StarBorder>
            {fetchError && <p className="text-red-400 text-sm mt-2 text-center">{fetchError}</p>}
          </div>
        </div>

        {/* Update User Section - Appears if userData is found */}
        {userData && (
          <div className="bg-soda-gray/70 backdrop-blur-xl p-6 md:p-8 rounded-xl shadow-2xl w-full max-w-xl">
            <h2 className="text-2xl md:text-3xl font-bold mb-6 text-soda-white text-center flex items-center justify-center">
              <FaUserEdit className="mr-3 h-7 w-7 text-soda-white" /> Update User: {userData.email}
            </h2>
            <form onSubmit={handleUpdateUser} className="space-y-4">
              <div>
                <label htmlFor="updateName" className="block text-sm font-medium text-soda-white mb-1">Name</label>
                <input id="updateName" type="text" value={updateName} onChange={(e) => setUpdateName(e.target.value)} className="w-full p-3 rounded-md bg-soda-black/50 border border-soda-white/20 text-soda-white focus:ring-soda-blue focus:border-soda-blue transition-all" />
              </div>
              <div>
                <label htmlFor="updateAsuId" className="block text-sm font-medium text-soda-white mb-1">ASU ID</label>
                <input id="updateAsuId" type="text" value={updateAsuId} onChange={(e) => setUpdateAsuId(e.target.value)} className="w-full p-3 rounded-md bg-soda-black/50 border border-soda-white/20 text-soda-white focus:ring-soda-blue focus:border-soda-blue transition-all" />
              </div>
              <div>
                <label htmlFor="updateAcademicStanding" className="block text-sm font-medium text-soda-white mb-1">Academic Standing</label>
                <input id="updateAcademicStanding" type="text" value={updateAcademicStanding} onChange={(e) => setUpdateAcademicStanding(e.target.value)} className="w-full p-3 rounded-md bg-soda-black/50 border border-soda-white/20 text-soda-white focus:ring-soda-blue focus:border-soda-blue transition-all" />
              </div>
              <div>
                <label htmlFor="updateMajor" className="block text-sm font-medium text-soda-white mb-1">Major</label>
                <input id="updateMajor" type="text" value={updateMajor} onChange={(e) => setUpdateMajor(e.target.value)} className="w-full p-3 rounded-md bg-soda-black/50 border border-soda-white/20 text-soda-white focus:ring-soda-blue focus:border-soda-blue transition-all" />
              </div>
              <StarBorder type="submit" disabled={loading} color="#34C759" speed="4s" className="w-full"> {/* Green for update */}
                {loading ? 'Updating...' : 'Save Changes'}
              </StarBorder>
              {updateError && <p className="text-red-400 text-sm mt-2 text-center">{updateError}</p>}
              {updateSuccessMessage && <p className="text-green-400 text-sm mt-2 text-center">{updateSuccessMessage}</p>}
            </form>
          </div>
        )}

        {/* Create New User Section */}
        <div className="bg-soda-gray/70 backdrop-blur-xl p-6 md:p-8 rounded-xl shadow-2xl w-full max-w-xl">
          <h2 className="text-2xl md:text-3xl font-bold mb-6 text-soda-white text-center flex items-center justify-center">
            <FaUserPlus className="mr-3 h-7 w-7 text-soda-red" /> Create New User
          </h2>
          <form onSubmit={handleCreateUser} className="space-y-4">
            <div>
              <label htmlFor="createEmail" className="block text-sm font-medium text-soda-white mb-1">Email</label>
              <input id="createEmail" type="email" value={createEmail} onChange={(e) => setCreateEmail(e.target.value)} className="w-full p-3 rounded-md bg-soda-black/50 border border-soda-white/20 text-soda-white focus:ring-soda-blue focus:border-soda-blue transition-all" placeholder="newuser@example.com" required />
            </div>
            <div>
              <label htmlFor="createName" className="block text-sm font-medium text-soda-white mb-1">Name</label>
              <input id="createName" type="text" value={createName} onChange={(e) => setCreateName(e.target.value)} className="w-full p-3 rounded-md bg-soda-black/50 border border-soda-white/20 text-soda-white focus:ring-soda-blue focus:border-soda-blue transition-all" placeholder="New User Name" required />
            </div>
            <div>
              <label htmlFor="createAsuId" className="block text-sm font-medium text-soda-white mb-1">ASU ID</label>
              <input id="createAsuId" type="text" value={createAsuId} onChange={(e) => setCreateAsuId(e.target.value)} className="w-full p-3 rounded-md bg-soda-black/50 border border-soda-white/20 text-soda-white focus:ring-soda-blue focus:border-soda-blue transition-all" placeholder="1234567890" required />
            </div>
            <div>
              <label htmlFor="createAcademicStanding" className="block text-sm font-medium text-soda-white mb-1">Academic Standing</label>
              <input id="createAcademicStanding" type="text" value={createAcademicStanding} onChange={(e) => setCreateAcademicStanding(e.target.value)} className="w-full p-3 rounded-md bg-soda-black/50 border border-soda-white/20 text-soda-white focus:ring-soda-blue focus:border-soda-blue transition-all" placeholder="Good Standing" required />
            </div>
            <div>
              <label htmlFor="createMajor" className="block text-sm font-medium text-soda-white mb-1">Major</label>
              <input id="createMajor" type="text" value={createMajor} onChange={(e) => setCreateMajor(e.target.value)} className="w-full p-3 rounded-md bg-soda-black/50 border border-soda-white/20 text-soda-white focus:ring-soda-blue focus:border-soda-blue transition-all" placeholder="Computer Science" required />
            </div>
            <StarBorder type="submit" disabled={loading} color="#FF3B30" speed="4s" className="w-full">
              {loading ? 'Creating...' : 'Create User'}
            </StarBorder>
            {createError && <p className="text-red-400 text-sm mt-2 text-center">{createError}</p>}
            {createSuccessMessage && <p className="text-green-400 text-sm mt-2 text-center">{createSuccessMessage}</p>}
          </form>
        </div>
      </div>
    </div>
  );
};

export default UserPage;
