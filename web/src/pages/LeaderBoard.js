import React, { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import Sidebar from '../components/SideBar';  // Import the Sidebar component
import apiClient from '../components/utils/axios';  // Axios instance for API requests
import useAuthToken from '../hooks/userAuth';  // Import custom hook for token validation

const Leaderboard = () => {
  useAuthToken();  // Call the custom hook for token validation and refresh

  const [leaderboardData, setLeaderboardData] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [isSidebarOpen, setIsSidebarOpen] = useState(false);  // Sidebar state
  const [showModal, setShowModal] = useState(false);  // Modal state
  const [selectedUser, setSelectedUser] = useState(null);  // Store selected user data for modal
  const [selectedUserEmail, setSelectedUserEmail] = useState('');  // Store selected user's email
  const [loadingUser, setLoadingUser] = useState(false);  // Loading state for modal content
  const [modalError, setModalError] = useState('');  // Error state for modal
  const [deleteLoading, setDeleteLoading] = useState(false);  // Loading state for delete operation
  const [showConfirmModal, setShowConfirmModal] = useState(false);  // State for confirmation modal
  const [pointToDelete, setPointToDelete] = useState(null);  // Store point to be deleted

  // Function to handle delete confirmation
  const handleDeleteClick = (event) => {
    setPointToDelete(event);
    setShowConfirmModal(true);
  };

  // Function to handle confirmed deletion
  const handleConfirmedDelete = async () => {
    if (pointToDelete) {
      await deletePoints(selectedUserEmail, pointToDelete);
      setShowConfirmModal(false);
      setPointToDelete(null);
    }
  };

  // Function to cancel deletion
  const handleCancelDelete = () => {
    setShowConfirmModal(false);
    setPointToDelete(null);
  };

  // Function to fetch and display the user details in the modal
  const viewUserDetails = async (identifier) => {
    setLoadingUser(true);
    setModalError('');
    setShowModal(true);  // Show modal
    setSelectedUserEmail(identifier);  // Store the identifier (email)
    try {
      const response = await apiClient.get(`/users/viewUser?user_identifier=${identifier}`);
      setSelectedUser(response.data);
      setLoadingUser(false);
    } catch (error) {
      setLoadingUser(false);
      if (error.response && error.response.data.error) {
        setModalError(error.response.data.error);
      } else {
        setModalError('An error occurred while fetching the user details.');
      }
    }
  };

  // Function to close the modal
  const closeModal = () => {
    setShowModal(false);
    setSelectedUser(null);
    setSelectedUserEmail('');  // Clear the email when closing modal
  };

  // Function to delete points
  const deletePoints = async (userEmail, event) => {
    setDeleteLoading(true);
    try {
      await apiClient.request({
        method: 'DELETE',
        url: '/points/delete_points',
        data: {
          user_email: selectedUserEmail,  // Use the stored email
          event: event
        }
      });
      // Refresh user details after deletion
      viewUserDetails(selectedUserEmail);
    } catch (error) {
      setModalError(error.response?.data?.error || 'Error deleting points');
    } finally {
      setDeleteLoading(false);
    }
  };

  // Fetch the leaderboard data
  useEffect(() => {
    const fetchLeaderboard = async () => {
      try {
        const response = await apiClient.get('/points/leaderboard');
        setLeaderboardData(response.data);
        setLoading(false);
      } catch (error) {
        setError('Error fetching leaderboard data.');
        setLoading(false);
      }
    };

    fetchLeaderboard();
  }, []);

  if (loading) {
    return <div className="text-center text-white">Loading...</div>;
  }

  if (error) {
    return <div className="text-center text-red-500">{error}</div>;
  }

  return (
    <div className="min-h-screen flex bg-gray-900 text-white">
      {/* Sidebar */}
      <Sidebar isSidebarOpen={isSidebarOpen} toggleSidebar={() => setIsSidebarOpen(!isSidebarOpen)} />

      {/* Main Content */}
      <div className={`flex-1 p-8 ${isSidebarOpen ? 'ml-60' : 'ml-16'}`}>
        <h1 className="text-4xl font-bold mb-8 text-center" style={{ color: '#ba3554' }}>Leaderboard</h1>

        {/* Leaderboard Table */}
        <div className="bg-gray-800 p-6 rounded-lg shadow-lg w-full max-w-4xl mx-auto">
          <table className="table-auto w-full text-left">
            <thead>
              <tr>
                <th className="px-4 py-2">Name</th>
                <th className="px-4 py-2">Identifier (Email/UUID)</th>
                <th className="px-4 py-2">Points</th>
              </tr>
            </thead>
            <tbody>
              {leaderboardData.map((user, index) => (
                <tr key={index} className="border-t border-gray-700">
                  <td className="px-4 py-2">{user.name}</td>
                  <td className="px-4 py-2">
                    <button
                      className="text-blue-400 hover:text-blue-500 underline"
                      onClick={() => viewUserDetails(user.identifier)}
                    >
                      {user.identifier}
                    </button>
                  </td>
                  <td className="px-4 py-2">{user.points}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>

        {/* Modal for viewing user details */}
        {showModal && (
          <div className="fixed inset-0 bg-black bg-opacity-75 flex items-center justify-center z-50 p-4">
            <div className="bg-gray-800 rounded-lg shadow-lg w-full max-w-4xl mx-auto relative max-h-[90vh] overflow-hidden flex flex-col">
              <div className="p-6 border-b border-gray-700">
                <button 
                  className="absolute top-4 right-4 text-gray-400 hover:text-white text-xl"
                  onClick={closeModal}
                >
                  ✖
                </button>
                <h2 className="text-2xl font-bold mb-4">{selectedUser?.name}</h2>
                <p><strong>UUID:</strong> {selectedUser?.uuid}</p>
                <p><strong>Academic Standing:</strong> {selectedUser?.academic_standing}</p>
                <p><strong>Major:</strong> {selectedUser?.major}</p>
              </div>

              <div className="flex-1 overflow-y-auto p-6">
                {loadingUser ? (
                  <div className="text-white">Loading user details...</div>
                ) : modalError ? (
                  <div className="text-red-500">{modalError}</div>
                ) : selectedUser && (
                  <>
                    <h3 className="text-xl font-bold mb-4">Points History</h3>
                    <div className="overflow-x-auto">
                      <table className="min-w-full table-auto">
                        <thead>
                          <tr className="bg-gray-700">
                            <th className="px-4 py-2">Event</th>
                            <th className="px-4 py-2">Points</th>
                            <th className="px-4 py-2">Awarded By</th>
                            <th className="px-4 py-2">Date</th>
                            <th className="px-4 py-2">Action</th>
                          </tr>
                        </thead>
                        <tbody>
                          {selectedUser.points_earned.map((point, index) => (
                            <tr key={index} className="border-t border-gray-600">
                              <td className="px-4 py-2">{point.event}</td>
                              <td className="px-4 py-2">{point.points}</td>
                              <td className="px-4 py-2">{point.awarded_by_officer}</td>
                              <td className="px-4 py-2">{point.timestamp}</td>
                              <td className="px-4 py-2">
                                <button
                                  onClick={() => handleDeleteClick(point.event)}
                                  disabled={deleteLoading}
                                  className="bg-red-600 hover:bg-red-700 text-white px-3 py-1 rounded disabled:opacity-50"
                                >
                                  {deleteLoading ? 'Deleting...' : 'Delete'}
                                </button>
                              </td>
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    </div>
                  </>
                )}
              </div>
            </div>
          </div>
        )}

        {/* Confirmation Modal */}
        {showConfirmModal && (
          <div className="fixed inset-0 bg-black bg-opacity-75 flex items-center justify-center z-[60] p-4">
            <div className="bg-gray-800 rounded-lg shadow-lg w-full max-w-md mx-auto p-6 relative">
              <h3 className="text-xl font-bold mb-4 text-white">Confirm Deletion</h3>
              <p className="text-gray-300 mb-6">
                Are you sure you want to delete points for the event "{pointToDelete}"?
                This action cannot be undone.
              </p>
              <div className="flex justify-end space-x-4">
                <button
                  onClick={handleCancelDelete}
                  className="px-4 py-2 bg-gray-600 text-white rounded hover:bg-gray-700"
                >
                  Cancel
                </button>
                <button
                  onClick={handleConfirmedDelete}
                  disabled={deleteLoading}
                  className="px-4 py-2 bg-red-600 text-white rounded hover:bg-red-700 disabled:opacity-50"
                >
                  {deleteLoading ? 'Deleting...' : 'Delete'}
                </button>
              </div>
            </div>
          </div>
        )}
      </div>
    </div>
  );
};

export default Leaderboard;
