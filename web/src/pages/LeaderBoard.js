import React, { useState, useEffect } from 'react';
import apiClient from '../components/utils/axios';
import useAuthToken from '../hooks/userAuth';
import useOrgNavigation from '../hooks/useOrgNavigation';
import { useAuth } from '../components/auth/AuthContext';
import OrganizationNavbar from '../components/shared/OrganizationNavbar';
import StarBorder from '../components/ui/StarBorder';
import { FaUsers, FaSignOutAlt, FaTachometerAlt, FaClipboardList, FaTrashAlt, FaTimes, FaCogs } from 'react-icons/fa';

const LeaderboardPage = () => {
  useAuthToken();
  const { currentOrg } = useAuth();
  const { 
    goToDashboard,
    goToUsers, 
    goToAddPoints,
    goToOCP,
    goToPanel,
    goToJeopardy 
  } = useOrgNavigation();

  const [leaderboardData, setLeaderboardData] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

  const [showModal, setShowModal] = useState(false);
  const [selectedUser, setSelectedUser] = useState(null);
  const [selectedUserEmail, setSelectedUserEmail] = useState('');
  const [loadingUser, setLoadingUser] = useState(false);
  const [modalError, setModalError] = useState('');
  const [deleteLoading, setDeleteLoading] = useState(false);
  const [showConfirmModal, setShowConfirmModal] = useState(false);
  const [pointToDelete, setPointToDelete] = useState(null);

  const handleDeleteClick = (event) => {
    setPointToDelete(event);
    setShowConfirmModal(true);
  };

  const handleConfirmedDelete = async () => {
    if (pointToDelete && selectedUserEmail) {
      setDeleteLoading(true);
      try {
        await apiClient.request({
          method: 'DELETE',
          url: '/api/points/delete_points',
          data: {
            user_email: selectedUserEmail,
            event: pointToDelete.event
          }
        });
        await viewUserDetails(selectedUserEmail);
        setShowConfirmModal(false);
        setPointToDelete(null);
      } catch (error) {
        setModalError(error.response?.data?.error || 'Error deleting points');
      } finally {
        setDeleteLoading(false);
      }
    }
  };

  const viewUserDetails = async (userEmail) => {
    setLoadingUser(true);
    setModalError('');
    try {
      const response = await apiClient.get(`/api/users/user?email=${encodeURIComponent(userEmail)}`);
      setSelectedUser(response.data);
      setSelectedUserEmail(userEmail);
      setShowModal(true);
    } catch (error) {
      setModalError(error.response?.data?.error || 'Failed to fetch user details');
    } finally {
      setLoadingUser(false);
    }
  };

  const fetchLeaderboard = async () => {
    try {
      setLoading(true);
      const response = await apiClient.get('/api/public/leaderboard');
      setLeaderboardData(response.data);
    } catch (error) {
      setError('Failed to fetch leaderboard data');
      console.error('Error fetching leaderboard:', error);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchLeaderboard();
  }, []);

  return (
    <OrganizationNavbar>
      <div className="max-w-7xl mx-auto">
        <div className="text-center mb-8">
          <h1 className="text-3xl font-bold mb-2">Leaderboard</h1>
          <p className="text-gray-400">View points rankings and user statistics</p>
        </div>

        {loading ? (
          <div className="flex items-center justify-center py-12">
            <div className="text-center">
              <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-blue-500 mx-auto mb-4"></div>
              <p className="text-gray-400">Loading leaderboard...</p>
            </div>
          </div>
        ) : error ? (
          <div className="text-center py-12">
            <p className="text-red-400">{error}</p>
          </div>
        ) : (
          <div className="bg-gray-900/50 backdrop-blur-sm rounded-xl border border-gray-700 p-6">
            <div className="overflow-x-auto">
              <table className="w-full text-left">
                <thead>
                  <tr className="border-b border-gray-700">
                    <th className="py-3 px-4 text-sm font-semibold text-gray-300">Rank</th>
                    <th className="py-3 px-4 text-sm font-semibold text-gray-300">User</th>
                    <th className="py-3 px-4 text-sm font-semibold text-gray-300">Email</th>
                    <th className="py-3 px-4 text-sm font-semibold text-gray-300">Points</th>
                    <th className="py-3 px-4 text-sm font-semibold text-gray-300">Actions</th>
                  </tr>
                </thead>
                <tbody>
                  {leaderboardData.map((user, index) => (
                    <tr key={user.email} className="border-b border-gray-800 hover:bg-gray-800/50 transition-colors">
                      <td className="py-4 px-4">
                        <div className="flex items-center">
                          <span className={`text-lg font-bold ${
                            index === 0 ? 'text-yellow-400' : 
                            index === 1 ? 'text-gray-300' : 
                            index === 2 ? 'text-amber-600' : 'text-gray-400'
                          }`}>
                            #{index + 1}
                          </span>
                        </div>
                      </td>
                      <td className="py-4 px-4">
                        <div className="flex items-center">
                          <div className="w-10 h-10 bg-gradient-to-br from-blue-500 to-purple-600 rounded-full flex items-center justify-center text-white font-bold text-sm">
                            {user.name ? user.name.charAt(0).toUpperCase() : 'U'}
                          </div>
                          <div className="ml-3">
                            <div className="text-white font-medium">{user.name || 'Unknown User'}</div>
                            <div className="text-sm text-gray-400">{user.asu_id || 'No ASU ID'}</div>
                          </div>
                        </div>
                      </td>
                      <td className="py-4 px-4 text-gray-300">{user.email}</td>
                      <td className="py-4 px-4">
                        <span className="text-lg font-bold text-green-400">{user.total_points || 0}</span>
                      </td>
                      <td className="py-4 px-4">
                        <button
                          onClick={() => viewUserDetails(user.email)}
                          className="px-3 py-1 bg-blue-600 hover:bg-blue-700 text-white text-sm rounded-md transition-colors"
                        >
                          View Details
                        </button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        )}

        {/* User Details Modal */}
        {showModal && (
          <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50">
            <div className="bg-gray-900 rounded-xl p-6 max-w-2xl w-full mx-4 max-h-[80vh] overflow-y-auto">
              <div className="flex justify-between items-center mb-4">
                <h2 className="text-xl font-bold text-white">User Details</h2>
                <button
                  onClick={() => setShowModal(false)}
                  className="text-gray-400 hover:text-white"
                >
                  <FaTimes size={24} />
                </button>
              </div>

              {loadingUser ? (
                <div className="text-center py-8">
                  <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-blue-500 mx-auto mb-4"></div>
                  <p className="text-gray-400">Loading user details...</p>
                </div>
              ) : modalError ? (
                <div className="text-red-400 text-center py-4">{modalError}</div>
              ) : selectedUser ? (
                <div className="space-y-4">
                  <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                    <div>
                      <label className="block text-sm font-medium text-gray-300 mb-1">Name</label>
                      <p className="text-white">{selectedUser.name || 'N/A'}</p>
                    </div>
                    <div>
                      <label className="block text-sm font-medium text-gray-300 mb-1">Email</label>
                      <p className="text-white">{selectedUser.email}</p>
                    </div>
                    <div>
                      <label className="block text-sm font-medium text-gray-300 mb-1">ASU ID</label>
                      <p className="text-white">{selectedUser.asu_id || 'N/A'}</p>
                    </div>
                    <div>
                      <label className="block text-sm font-medium text-gray-300 mb-1">Major</label>
                      <p className="text-white">{selectedUser.major || 'N/A'}</p>
                    </div>
                  </div>

                  <div>
                    <label className="block text-sm font-medium text-gray-300 mb-2">Points History</label>
                    <div className="space-y-2">
                      {selectedUser.points && selectedUser.points.length > 0 ? (
                        selectedUser.points.map((point, index) => (
                          <div key={index} className="flex items-center justify-between p-3 bg-gray-800 rounded-lg">
                            <div>
                              <div className="text-white font-medium">{point.event}</div>
                              <div className="text-sm text-gray-400">{point.date}</div>
                            </div>
                            <div className="flex items-center space-x-2">
                              <span className="text-green-400 font-bold">+{point.points}</span>
                              <button
                                onClick={() => handleDeleteClick(point)}
                                className="text-red-400 hover:text-red-300"
                                title="Delete this point entry"
                              >
                                <FaTrashAlt size={16} />
                              </button>
                            </div>
                          </div>
                        ))
                      ) : (
                        <p className="text-gray-400 text-center py-4">No points history available</p>
                      )}
                    </div>
                  </div>
                </div>
              ) : null}
            </div>
          </div>
        )}

        {/* Confirmation Modal */}
        {showConfirmModal && (
          <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50">
            <div className="bg-gray-900 rounded-xl p-6 max-w-md w-full mx-4">
              <h3 className="text-lg font-bold text-white mb-4">Confirm Deletion</h3>
              <p className="text-gray-300 mb-6">
                Are you sure you want to delete the points for "{pointToDelete?.event}"?
                This action cannot be undone.
              </p>
              <div className="flex space-x-3">
                <button
                  onClick={() => setShowConfirmModal(false)}
                  className="flex-1 px-4 py-2 bg-gray-600 hover:bg-gray-700 text-white rounded-md transition-colors"
                >
                  Cancel
                </button>
                <button
                  onClick={handleConfirmedDelete}
                  disabled={deleteLoading}
                  className="flex-1 px-4 py-2 bg-red-600 hover:bg-red-700 disabled:bg-gray-600 text-white rounded-md transition-colors"
                >
                  {deleteLoading ? 'Deleting...' : 'Delete'}
                </button>
              </div>
            </div>
          </div>
        )}
      </div>
    </OrganizationNavbar>
  );
};

export default LeaderboardPage;