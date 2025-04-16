import React, { useState } from 'react';
import Sidebar from '../components/SideBar';
import apiClient from '../components/utils/axios';
import useAuthToken from '../hooks/userAuth';

const CreateUserPage = () => {
  useAuthToken();

  const [email, setEmail] = useState('');
  const [name, setName] = useState('');
  const [asuId, setAsuId] = useState('');
  const [academicStanding, setAcademicStanding] = useState('');
  const [major, setMajor] = useState('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [successMessage, setSuccessMessage] = useState('');
  const [isSidebarOpen, setIsSidebarOpen] = useState(false);

  const createUser = async (e) => {
    e.preventDefault();
    setLoading(true);
    setError('');
    setSuccessMessage('');
  
    // Validate fields
    if (!email || !name || !asuId || !academicStanding || !major) {
      setError('All fields are required. Please fill out the form completely.');
      setLoading(false);
      return;
    }
  
    const data = {
      email,
      name,
      asu_id: asuId,
      academic_standing: academicStanding,
      major,
    };
  
    console.log(data);
    try {
      const response = await apiClient.post('users/createUser', data);
      setSuccessMessage(response.data.message);
      setEmail('');
      setName('');
      setAsuId('');
      setAcademicStanding('');
      setMajor('');
    } catch (error) {
      if (error.response && error.response.data.error) {
        setError(error.response.data.error);
      } else {
        setError('An error occurred while creating the user.');
      }
    } finally {
      setLoading(false);
    }
  };
  

  return (
    <div className="min-h-screen flex bg-gray-900 text-white">
      <Sidebar isSidebarOpen={isSidebarOpen} toggleSidebar={() => setIsSidebarOpen(!isSidebarOpen)} />

      <div className={`flex-1 p-8 ${isSidebarOpen ? 'ml-60' : 'ml-16'}`}>
        <h1 className="text-4xl font-bold mb-8 text-center" style={{ color: '#ba3554' }}>Create New User</h1>

        <div className="bg-gray-800 p-6 rounded-lg shadow-lg w-full max-w-lg mx-auto">
          <h2 className="text-2xl font-bold mb-4">User Information</h2>

          {error && <p className="text-red-500 mb-4">{error}</p>}
          {successMessage && <p className="text-green-500 mb-4">{successMessage}</p>}

          <form onSubmit={createUser}>
            <div className="mb-4">
              <label className="block text-white mb-2">Email</label>
              <input
                type="email"
                className="w-full p-2 rounded-md bg-gray-700 text-white"
                placeholder="Enter email"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
              />
            </div>

            <div className="mb-4">
              <label className="block text-white mb-2">Name</label>
              <input
                type="text"
                className="w-full p-2 rounded-md bg-gray-700 text-white"
                placeholder="Enter name"
                value={name}
                onChange={(e) => setName(e.target.value)}
              />
            </div>

            <div className="mb-4">
              <label className="block text-white mb-2">ASU ID</label>
              <input
                type="text"
                className="w-full p-2 rounded-md bg-gray-700 text-white"
                placeholder="Enter ASU ID"
                value={asuId}
                onChange={(e) => setAsuId(e.target.value)}
              />
            </div>

            <div className="mb-4">
              <label className="block text-white mb-2">Academic Standing</label>
              <input
                type="text"
                className="w-full p-2 rounded-md bg-gray-700 text-white"
                placeholder="Enter academic standing"
                value={academicStanding}
                onChange={(e) => setAcademicStanding(e.target.value)}
              />
            </div>

            <div className="mb-4">
              <label className="block text-white mb-2">Major</label>
              <input
                type="text"
                className="w-full p-2 rounded-md bg-gray-700 text-white"
                placeholder="Enter major"
                value={major}
                onChange={(e) => setMajor(e.target.value)}
              />
            </div>

            <button
              type="submit"
              className="w-full py-2 px-4 bg-green-600 hover:bg-green-700 rounded-md text-white font-semibold"
              disabled={loading}
            >
              {loading ? 'Creating...' : 'Create User'}
            </button>
          </form>
        </div>
      </div>
    </div>
  );
};

export default CreateUserPage;
