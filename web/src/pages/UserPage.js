import React, { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import apiClient from '../components/utils/axios';
import useAuthToken from '../hooks/userAuth';
import OrganizationNavbar from '../components/shared/OrganizationNavbar';
import StarBorder from '../components/ui/StarBorder';
import { FaSearch, FaUserPlus } from 'react-icons/fa';

const UserPage = () => {
  useAuthToken();
  const navigate = useNavigate();

  // State for finding/updating user
  const [searchEmail, setSearchEmail] = useState('');
  const [userData, setUserData] = useState(null);
  const [loadingFetch, setLoadingFetch] = useState(false);
  const [loadingUpdate, setLoadingUpdate] = useState(false);
  const [updateError, setUpdateError] = useState('');
  const [updateSuccess, setUpdateSuccess] = useState('');

  // State for user form fields (used for both update and create)
  const [name, setName] = useState('');
  const [asuId, setAsuId] = useState('');
  const [academicStanding, setAcademicStanding] = useState('');
  const [major, setMajor] = useState('');
  const [currentEmailForUpdate, setCurrentEmailForUpdate] = useState(''); // Stores the email of the user being updated

  // State for creating user
  const [createEmail, setCreateEmail] = useState('');
  const [loadingCreate, setLoadingCreate] = useState(false);
  const [createError, setCreateError] = useState('');
  const [createSuccess, setCreateSuccess] = useState('');

  const resetUpdateFormFields = () => {
    setName('');
    setAsuId('');
    setAcademicStanding('');
    setMajor('');
    setCurrentEmailForUpdate('');
  };

  const resetCreateFormFields = () => {
    setCreateEmail('');
    // Keep name, asuId, etc. if you want to prefill from a previous search, or clear them too
    // setName(''); setAsuId(''); setAcademicStanding(''); setMajor(''); 
  };

  const fetchUser = async () => {
    if (!searchEmail) {
      setUpdateError('Please enter an email to search.');
      return;
    }
    setLoadingFetch(true);
    setUpdateError('');
    setUpdateSuccess('');
    setUserData(null);
    resetUpdateFormFields();

    try {
      const response = await apiClient.get(`/users/user?email=${searchEmail}`);
      setUserData(response.data);
      setName(response.data.name || '');
      setAsuId(response.data.asu_id || '');
      setAcademicStanding(response.data.academic_standing || '');
      setMajor(response.data.major || '');
      setCurrentEmailForUpdate(searchEmail); // Set the email for the update form
    } catch (error) {
      if (error.response && error.response.status === 404) {
        setUpdateError('User not found. You can create this user or update their details if they exist under a different email.');
        setUserData({}); // To show the form for potential creation/update
        setCurrentEmailForUpdate(searchEmail); // Allow updating this email if the intent changes to create
      } else {
        setUpdateError(error.response?.data?.error || 'Error fetching user.');
      }
    } finally {
      setLoadingFetch(false);
    }
  };

  const handleUpdateUser = async (e) => {
    e.preventDefault();
    if (!currentEmailForUpdate) {
        setUpdateError('No user selected or email specified for update.');
        return;
    }
    setLoadingUpdate(true);
    setUpdateError('');
    setUpdateSuccess('');

    const dataToUpdate = {
      email: currentEmailForUpdate, // The email of the user to update
      name,
      asu_id: asuId,
      academic_standing: academicStanding,
      major,
    };

    try {
      // Using POST to /users/user which acts as an upsert endpoint
      const response = await apiClient.post('/users/user', dataToUpdate);
      setUpdateSuccess(response.data.message || 'User updated successfully!');
      // Optionally re-fetch user data or clear form
      // fetchUser(); // to refresh data if needed, ensure searchEmail is still currentEmailForUpdate
    } catch (error) {
      setUpdateError(error.response?.data?.error || 'Error updating user.');
    } finally {
      setLoadingUpdate(false);
    }
  };

  const handleCreateUser = async (e) => {
    e.preventDefault();
    if (!createEmail || !name || !asuId || !academicStanding || !major) {
      setCreateError('All fields are required for creating a user.');
      return;
    }
    setLoadingCreate(true);
    setCreateError('');
    setCreateSuccess('');

    const data = { email: createEmail, name, asu_id: asuId, academic_standing: academicStanding, major };

    try {
      const response = await apiClient.post('/api/users/createUser', data);
      setCreateSuccess(response.data.message || 'User created successfully!');
      resetCreateFormFields(); // Clear create form
      // also clear shared fields if they were used for creation
      setName(''); setAsuId(''); setAcademicStanding(''); setMajor('');
    } catch (error) {
      setCreateError(error.response?.data?.error || 'Error creating user.');
    } finally {
      setLoadingCreate(false);
    }
  };
  

  return (
    <OrganizationNavbar>
      <div className="container mt-10 mx-auto px-4 py-12 md:py-16 flex flex-col lg:flex-row lg:space-x-8 space-y-8 lg:space-y-0 items-start justify-center">
        {/* Section 1: Find and Update User */}
        <div className="bg-soda-gray/70 backdrop-blur-xl p-6 md:p-8 rounded-xl shadow-2xl w-full max-w-lg">
          <h2 className="text-2xl md:text-3xl font-bold mb-6 text-soda-white text-center flex items-center justify-center">
            <FaSearch className="mr-3 h-7 w-7 text-soda-blue" /> Find & Update User
          </h2>
          <div className="space-y-4 mb-6">
            <label htmlFor="searchEmail" className="block text-sm font-medium text-soda-white mb-1">User Email to Find/Update</label>
          <input
              id="searchEmail"
            type="email"
              className="w-full p-3 rounded-md bg-soda-black/50 border border-soda-white/20 text-soda-white focus:ring-soda-blue focus:border-soda-blue transition-all"
            placeholder="Enter user email"
              value={searchEmail}
              onChange={(e) => setSearchEmail(e.target.value)}
          />
            <StarBorder onClick={fetchUser} disabled={loadingFetch} color="#007AFF" speed="4s" className="w-full">
              {loadingFetch ? 'Searching...' : 'Find User'}
            </StarBorder>
        </div>

          {updateError && <p className="text-red-400 mb-4 text-sm text-center">{updateError}</p>}
          {updateSuccess && <p className="text-green-400 mb-4 text-sm text-center">{updateSuccess}</p>}
          
          {/* Update Form - shows if userData is present or if user not found (to allow filling details) */}
          {(userData || (updateError && updateError.includes("User not found"))) && (
            <form onSubmit={handleUpdateUser} className="space-y-4 pt-4 border-t border-soda-white/10">
                 <p className="text-xs text-soda-white/70 mb-2">Editing details for: {currentEmailForUpdate || 'N/A'}</p>
              <div>
                <label htmlFor="updateName" className="block text-sm font-medium text-soda-white mb-1">Name</label>
                <input id="updateName" type="text" className="w-full p-3 rounded-md bg-soda-black/50 border border-soda-white/20 text-soda-white focus:ring-soda-blue focus:border-soda-blue transition-all" value={name} onChange={(e) => setName(e.target.value)} />
              </div>
              <div>
                <label htmlFor="updateAsuId" className="block text-sm font-medium text-soda-white mb-1">ASU ID</label>
                <input id="updateAsuId" type="text" className="w-full p-3 rounded-md bg-soda-black/50 border border-soda-white/20 text-soda-white focus:ring-soda-blue focus:border-soda-blue transition-all" value={asuId} onChange={(e) => setAsuId(e.target.value)} />
              </div>
              <div>
                <label htmlFor="updateAcademicStanding" className="block text-sm font-medium text-soda-white mb-1">Academic Standing</label>
                <input id="updateAcademicStanding" type="text" className="w-full p-3 rounded-md bg-soda-black/50 border border-soda-white/20 text-soda-white focus:ring-soda-blue focus:border-soda-blue transition-all" value={academicStanding} onChange={(e) => setAcademicStanding(e.target.value)} />
              </div>
              <div>
                <label htmlFor="updateMajor" className="block text-sm font-medium text-soda-white mb-1">Major</label>
                <input id="updateMajor" type="text" className="w-full p-3 rounded-md bg-soda-black/50 border border-soda-white/20 text-soda-white focus:ring-soda-blue focus:border-soda-blue transition-all" value={major} onChange={(e) => setMajor(e.target.value)} />
              </div>
              <StarBorder type="submit" disabled={loadingUpdate} color="#34C759" speed="4s" className="w-full"> {/* Green for update */}
                {loadingUpdate ? 'Updating...' : 'Save User Details'}
              </StarBorder>
            </form>
          )}
              </div>

        {/* Section 2: Create New User */}
        <div className="bg-soda-gray/70 backdrop-blur-xl p-6 md:p-8 rounded-xl shadow-2xl w-full max-w-lg">
          <h2 className="text-2xl md:text-3xl font-bold mb-6 text-soda-white text-center flex items-center justify-center">
            <FaUserPlus className="mr-3 h-7 w-7 text-soda-red" /> Create New User
          </h2>
          {createError && <p className="text-red-400 mb-4 text-sm text-center">{createError}</p>}
          {createSuccess && <p className="text-green-400 mb-4 text-sm text-center">{createSuccess}</p>}
          <form onSubmit={handleCreateUser} className="space-y-4">
            <div>
              <label htmlFor="createEmail" className="block text-sm font-medium text-soda-white mb-1">User Email</label>
              <input id="createEmail" type="email" placeholder="new.user@example.com" className="w-full p-3 rounded-md bg-soda-black/50 border border-soda-white/20 text-soda-white focus:ring-soda-red focus:border-soda-red transition-all" value={createEmail} onChange={(e) => setCreateEmail(e.target.value)} required />
            </div>
             {/* Fields for create - can reuse state from update form or have separate ones if logic differs */}
            <div>
                <label htmlFor="createName" className="block text-sm font-medium text-soda-white mb-1">Name</label>
                <input id="createName" type="text" className="w-full p-3 rounded-md bg-soda-black/50 border border-soda-white/20 text-soda-white focus:ring-soda-red focus:border-soda-red transition-all" value={name} onChange={(e) => setName(e.target.value)} placeholder="New User Name" required/>
            </div>
            <div>
                <label htmlFor="createAsuId" className="block text-sm font-medium text-soda-white mb-1">ASU ID</label>
                <input id="createAsuId" type="text" className="w-full p-3 rounded-md bg-soda-black/50 border border-soda-white/20 text-soda-white focus:ring-soda-red focus:border-soda-red transition-all" value={asuId} onChange={(e) => setAsuId(e.target.value)} placeholder="ASU ID" required/>
            </div>
            <div>
                <label htmlFor="createAcademicStanding" className="block text-sm font-medium text-soda-white mb-1">Academic Standing</label>
                <input id="createAcademicStanding" type="text" className="w-full p-3 rounded-md bg-soda-black/50 border border-soda-white/20 text-soda-white focus:ring-soda-red focus:border-soda-red transition-all" value={academicStanding} onChange={(e) => setAcademicStanding(e.target.value)} placeholder="e.g., Sophomore" required/>
            </div>
            <div>
                <label htmlFor="createMajor" className="block text-sm font-medium text-soda-white mb-1">Major</label>
                <input id="createMajor" type="text" className="w-full p-3 rounded-md bg-soda-black/50 border border-soda-white/20 text-soda-white focus:ring-soda-red focus:border-soda-red transition-all" value={major} onChange={(e) => setMajor(e.target.value)} placeholder="e.g., Computer Science" required/>
            </div>
            <StarBorder type="submit" disabled={loadingCreate} color="#FF3B30" speed="4s" className="w-full">
              {loadingCreate ? 'Creating...' : 'Create User'}
            </StarBorder>
            </form>
          </div>
      </div>
    </OrganizationNavbar>
  );
};

export default UserPage;