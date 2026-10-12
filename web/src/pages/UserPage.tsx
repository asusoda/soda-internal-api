import { useState, type FormEvent } from 'react';
import axios from 'axios';
import apiClient from '../components/utils/axios';
import useAuthToken from '../hooks/userAuth';
import { useAuth } from '../components/auth/AuthContext';
import OrganizationNavbar from '../components/shared/OrganizationNavbar';
import StarBorder from '../components/ui/StarBorder';
import { FaSearch, FaUserPlus } from 'react-icons/fa';
import type { ApiError } from '../types';
import { changedMemberFields } from '../pointsTypes';
import type { MemberEditFields, MessageResponse, UserPointsResponse } from '../pointsTypes';

const EMPTY_FIELDS: MemberEditFields = { name: '', asu_id: '', academic_standing: '', major: '' };

const UserPage = () => {
  useAuthToken();
  const { currentOrg } = useAuth();

  // State for finding/updating user
  const [searchEmail, setSearchEmail] = useState('');
  const [userData, setUserData] = useState<UserPointsResponse['user'] | Record<string, never> | null>(null);
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
  // The form values as loaded, so that an update sends only the fields the officer changed.
  const [loadedFields, setLoadedFields] = useState<MemberEditFields>(EMPTY_FIELDS);

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
    setLoadedFields(EMPTY_FIELDS);
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
    if (!currentOrg?.prefix) {
      setUpdateError('No organization selected.');
      return;
    }
    
    setLoadingFetch(true);
    setUpdateError('');
    setUpdateSuccess('');
    setUserData(null);
    resetUpdateFormFields();

    try {
      // Use the new consolidated endpoint to get user details
      const response = await apiClient.get<UserPointsResponse>(`/api/points/${currentOrg.prefix}/users/${searchEmail}/points`);
      const { user } = response.data;
      const fields: MemberEditFields = {
        name: user.name || '',
        asu_id: user.asu_id || '',
        academic_standing: user.academic_standing || '',
        major: user.major || '',
      };
      setUserData(user);
      setName(fields.name);
      setAsuId(fields.asu_id);
      setAcademicStanding(fields.academic_standing);
      setMajor(fields.major);
      setLoadedFields(fields);
      setCurrentEmailForUpdate(searchEmail);
    } catch (error) {
      if (axios.isAxiosError<ApiError>(error) && error.response && error.response.status === 404) {
        setUpdateError('User not found. You can create this user or update their details if they exist under a different email.');
        setUserData({}); // To show the form for potential creation/update
        setCurrentEmailForUpdate(searchEmail);
      } else {
        setUpdateError((axios.isAxiosError<ApiError>(error) && error.response?.data?.error) || 'Error fetching user.');
      }
    } finally {
      setLoadingFetch(false);
    }
  };

  const handleUpdateUser = async (e: FormEvent<HTMLFormElement>) => {
    e.preventDefault();
    if (!currentEmailForUpdate) {
        setUpdateError('No user selected or email specified for update.');
        return;
    }
    if (!currentOrg?.prefix) {
        setUpdateError('No organization selected.');
        return;
    }
    
    setLoadingUpdate(true);
    setUpdateError('');
    setUpdateSuccess('');

    const dataToUpdate = changedMemberFields(loadedFields, {
      name,
      asu_id: asuId,
      academic_standing: academicStanding,
      major,
    });
    if (Object.keys(dataToUpdate).length === 0) {
      setUpdateSuccess('No changes to save.');
      setLoadingUpdate(false);
      return;
    }

    try {
      // Use the new consolidated endpoint for updating user fields
      const response = await apiClient.put<MessageResponse>(`/api/points/${currentOrg.prefix}/users/${currentEmailForUpdate}`, dataToUpdate);
      setUpdateSuccess(response.data.message || 'User updated successfully!');
      // Refresh user data to show updated information
      setTimeout(() => {
        fetchUser();
      }, 1000);
    } catch (error) {
      setUpdateError((axios.isAxiosError<ApiError>(error) && error.response?.data?.error) || 'Error updating user.');
    } finally {
      setLoadingUpdate(false);
    }
  };

  const handleCreateUser = async (e: FormEvent<HTMLFormElement>) => {
    e.preventDefault();
    if (!createEmail || !name) {
      setCreateError('Email and name are required for creating a user.');
      return;
    }
    if (!currentOrg?.prefix) {
      setCreateError('No organization selected.');
      return;
    }
    
    setLoadingCreate(true);
    setCreateError('');
    setCreateSuccess('');

    const data = { 
      email: createEmail, 
      name, 
      asu_id: asuId || undefined, // Don't send empty string, let it be undefined
      academic_standing: academicStanding || undefined, 
      major: major || undefined 
    };

    try {
      // Use the new consolidated endpoint for creating users
      const response = await apiClient.post<MessageResponse>(`/api/points/${currentOrg.prefix}/users`, data);
      setCreateSuccess(response.data.message || 'User created successfully!');
      resetCreateFormFields(); // Clear create form
      // also clear shared fields if they were used for creation
      setName(''); setAsuId(''); setAcademicStanding(''); setMajor('');
    } catch (error) {
      setCreateError((axios.isAxiosError<ApiError>(error) && error.response?.data?.error) || 'Error creating user.');
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
            <StarBorder onClick={fetchUser} disabled={loadingFetch} color="#007AFF" className="w-full">
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
                <label htmlFor="createAsuId" className="block text-sm font-medium text-soda-white mb-1">ASU ID (Optional)</label>
                <input id="createAsuId" type="text" className="w-full p-3 rounded-md bg-soda-black/50 border border-soda-white/20 text-soda-white focus:ring-soda-red focus:border-soda-red transition-all" value={asuId} onChange={(e) => setAsuId(e.target.value)} placeholder="ASU ID (Optional)"/>
            </div>
            <div>
                <label htmlFor="createAcademicStanding" className="block text-sm font-medium text-soda-white mb-1">Academic Standing (Optional)</label>
                <input id="createAcademicStanding" type="text" className="w-full p-3 rounded-md bg-soda-black/50 border border-soda-white/20 text-soda-white focus:ring-soda-red focus:border-soda-red transition-all" value={academicStanding} onChange={(e) => setAcademicStanding(e.target.value)} placeholder="e.g., Sophomore"/>
            </div>
            <div>
                <label htmlFor="createMajor" className="block text-sm font-medium text-soda-white mb-1">Major (Optional)</label>
                <input id="createMajor" type="text" className="w-full p-3 rounded-md bg-soda-black/50 border border-soda-white/20 text-soda-white focus:ring-soda-red focus:border-soda-red transition-all" value={major} onChange={(e) => setMajor(e.target.value)} placeholder="e.g., Computer Science"/>
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