import React, { useState, useEffect } from 'react';
import apiClient from '../components/utils/axios';
import useAuthToken from '../hooks/userAuth';
import useOrgNavigation from '../hooks/useOrgNavigation';
import { useAuth } from '../components/auth/AuthContext';
import Orb from '../components/ui/Orb';
import { Menu, MenuItem, HoveredLink } from '../components/ui/navbar-menu';
import StarBorder from '../components/ui/StarBorder';
import OrganizationSwitcher from '../components/OrganizationSwitcher';
import { FaUsers, FaSignOutAlt, FaTachometerAlt, FaClipboardList, FaTrashAlt, FaTimes, FaCogs } from 'react-icons/fa';

const LeaderboardPage = () => {
  useAuthToken();
  const { logout, currentOrg } = useAuth();
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
  const [activeNavItem, setActiveNavItem] = useState(null);

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

  if (loading) {
    return (
      <div className="min-h-screen bg-black flex items-center justify-center">
        <div className="text-center text-white">
          <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-white mx-auto mb-4"></div>
          <p>Loading leaderboard...</p>
        </div>
      </div>
    );
  }

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
                    <h1 className="text-xl font-bold">{currentOrg.name} Leaderboard</h1>
                    <p className="text-sm text-gray-400">/{currentOrg.prefix}</p>
                  </div>
                </div>
              )}
            </div>

            {/* Center - Navigation Menu */}
            <div className="flex items-center space-x-6">
              <MenuItem setActive={setActiveNavItem} active={activeNavItem} item="Dashboard">
                <div className="flex flex-col space-y-4 text-sm">
                  <HoveredLink onClick={goToDashboard}>
                    <FaTachometerAlt className="inline mr-2" />Dashboard
                  </HoveredLink>
                  <HoveredLink onClick={goToUsers}>
                    <FaUsers className="inline mr-2" />User Management
                  </HoveredLink>
                  <HoveredLink onClick={goToOCP}>
                    <FaClipboardList className="inline mr-2" />OCP Details
                  </HoveredLink>
                </div>
              </MenuItem>

              <MenuItem setActive={setActiveNavItem} active={activeNavItem} item="Points">
                <div className="flex flex-col space-y-4 text-sm">
                  <HoveredLink onClick={goToAddPoints}>
                    <FaUsers className="inline mr-2" />Add Points
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
                className="flex items-center space-x-2 px-3 py-2 rounded-md text-sm font-medium text-gray-300 hover:text-white hover:bg-gray-700"
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
          {error && (
            <div className="bg-red-900/50 border border-red-500 text-red-200 px-4 py-3 rounded mb-6">
              {error}
            </div>
          )}

          {/* Leaderboard Table */}
          <div className="bg-gray-900/50 backdrop-blur-sm rounded-lg border border-gray-700 overflow-hidden">
            <div className="px-6 py-4 bg-gray-800/50 border-b border-gray-700">
              <h2 className="text-2xl font-bold">Points Leaderboard</h2>
              <p className="text-gray-400 mt-1">Top performers in {currentOrg?.name || 'the organization'}</p>
            </div>
            
            <div className="overflow-x-auto">
              <table className="w-full">
                <thead className="bg-gray-800/30">
                  <tr>
                    <th className="px-6 py-3 text-left text-xs font-medium text-gray-300 uppercase tracking-wider">Rank</th>
                    <th className="px-6 py-3 text-left text-xs font-medium text-gray-300 uppercase tracking-wider">User</th>
                    <th className="px-6 py-3 text-left text-xs font-medium text-gray-300 uppercase tracking-wider">Total Points</th>
                    <th className="px-6 py-3 text-left text-xs font-medium text-gray-300 uppercase tracking-wider">Actions</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-gray-700">
                  {leaderboardData.map((user, index) => (
                    <tr key={user.uuid} className="hover:bg-gray-800/20">
                      <td className="px-6 py-4 whitespace-nowrap">
                        <div className="flex items-center">
                          <span className="text-lg font-bold">#{index + 1}</span>
                          {index < 3 && (
                            <span className="ml-2 text-2xl">
                              {index === 0 ? '🥇' : index === 1 ? '🥈' : '🥉'}
                            </span>
                          )}
                        </div>
                      </td>
                      <td className="px-6 py-4 whitespace-nowrap">
                        <div className="text-sm font-medium text-white">{user.name}</div>
                        <div className="text-sm text-gray-400">{user.uuid}</div>
                      </td>
                      <td className="px-6 py-4 whitespace-nowrap">
                        <div className="text-lg font-bold text-blue-400">{user.total_points}</div>
                      </td>
                      <td className="px-6 py-4 whitespace-nowrap">
                        <button
                          onClick={() => viewUserDetails(user.uuid)}
                          className="bg-blue-600 hover:bg-blue-700 text-white px-3 py-1 rounded text-sm transition-colors"
                          disabled={loadingUser}
                        >
                          {loadingUser ? 'Loading...' : 'View Details'}
                        </button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        </div>
      </div>

      {/* User Details Modal */}
      {showModal && selectedUser && (
        <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50 p-4">
          <div className="bg-gray-900 rounded-lg max-w-2xl w-full max-h-[80vh] overflow-y-auto">
            <div className="p-6 border-b border-gray-700">
              <div className="flex justify-between items-center">
                <h3 className="text-xl font-bold">{selectedUser.name} - Points Details</h3>
                <button
                  onClick={() => setShowModal(false)}
                  className="text-gray-400 hover:text-white"
                >
                  <FaTimes />
                </button>
              </div>
            </div>
            
            <div className="p-6">
              {modalError && (
                <div className="bg-red-900/50 border border-red-500 text-red-200 px-4 py-3 rounded mb-4">
                  {modalError}
                </div>
              )}
              
              <div className="mb-4">
                <p><strong>Total Points:</strong> {selectedUser.total_points}</p>
                <p><strong>Email:</strong> {selectedUser.email}</p>
              </div>
              
              {selectedUser.points && selectedUser.points.length > 0 && (
                <div>
                  <h4 className="text-lg font-semibold mb-2">Points History</h4>
                  <div className="space-y-2">
                    {selectedUser.points.map((point, idx) => (
                      <div key={idx} className="bg-gray-800 p-3 rounded flex justify-between items-center">
                        <div>
                          <p><strong>Event:</strong> {point.event}</p>
                          <p><strong>Points:</strong> {point.points}</p>
                          <p><strong>Awarded by:</strong> {point.awarded_by_officer}</p>
                          <p><strong>Date:</strong> {new Date(point.awarded_at).toLocaleDateString()}</p>
                        </div>
                        <button
                          onClick={() => handleDeleteClick(point)}
                          className="bg-red-600 hover:bg-red-700 text-white p-2 rounded"
                          disabled={deleteLoading}
                        >
                          <FaTrashAlt />
                        </button>
                      </div>
                    ))}
                  </div>
                </div>
              )}
            </div>
          </div>
        </div>
      )}

      {/* Confirm Delete Modal */}
      {showConfirmModal && (
        <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50">
          <div className="bg-gray-900 rounded-lg p-6 max-w-md w-full mx-4">
            <h3 className="text-lg font-bold mb-4">Confirm Delete</h3>
            <p className="mb-6">Are you sure you want to delete this points entry?</p>
            <div className="flex space-x-4">
              <button
                onClick={handleConfirmedDelete}
                disabled={deleteLoading}
                className="bg-red-600 hover:bg-red-700 text-white px-4 py-2 rounded flex-1"
              >
                {deleteLoading ? 'Deleting...' : 'Delete'}
              </button>
              <button
                onClick={() => setShowConfirmModal(false)}
                className="bg-gray-600 hover:bg-gray-700 text-white px-4 py-2 rounded flex-1"
              >
                Cancel
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};

export default LeaderboardPage;