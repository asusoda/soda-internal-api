import React, { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import apiClient from '../components/utils/axios';
import useAuthToken from '../hooks/userAuth';
import Orb from '../components/ui/Orb';
import { Menu, MenuItem, HoveredLink } from '../components/ui/navbar-menu';
import StarBorder from '../components/ui/StarBorder'; // For potential future use, or if styling modal buttons
import { FaUsers, FaSignOutAlt, FaTachometerAlt, FaClipboardList, FaTrashAlt, FaTimes } from 'react-icons/fa'; // Added FaTimes for close icon

const LeaderboardPage = () => {
  useAuthToken();
  const navigate = useNavigate();

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
    if (pointToDelete && selectedUserEmail) { // Ensure selectedUserEmail is available
      setDeleteLoading(true);
      try {
        await apiClient.request({
          method: 'DELETE',
          url: '/points/delete_points',
          data: {
            user_email: selectedUserEmail,
            event: pointToDelete.event // Assuming pointToDelete is an object with an event property
          }
        });
        await viewUserDetails(selectedUserEmail); // Refresh after delete
      setShowConfirmModal(false);
      setPointToDelete(null);
      } catch (error) {
        setModalError(error.response?.data?.error || 'Error deleting points');
      } finally {
        setDeleteLoading(false);
      }
    }
  };

  const handleCancelDelete = () => {
    setShowConfirmModal(false);
    setPointToDelete(null);
  };

  const viewUserDetails = async (identifier) => {
    setSelectedUserEmail(identifier); // Set email right away for delete context
    setLoadingUser(true);
    setModalError('');
    setShowModal(true);
    try {
      const response = await apiClient.get(`/users/viewUser?user_identifier=${identifier}`);
      setSelectedUser(response.data);
    } catch (error) {
      if (error.response && error.response.data.error) {
        setModalError(error.response.data.error);
      } else {
        setModalError('An error occurred while fetching user details.');
      }
    } finally {
      setLoadingUser(false);
    }
  };

  const closeModal = () => {
    setShowModal(false);
    setSelectedUser(null);
    // selectedUserEmail is kept if needed for other operations or cleared if not
  };

  useEffect(() => {
    const fetchLeaderboard = async () => {
      setLoading(true);
      try {
        const response = await apiClient.get('/points/leaderboard');
        setLeaderboardData(response.data);
      } catch (error) {
        setError(error.response?.data?.error || 'Error fetching leaderboard data.');
      } finally {
        setLoading(false);
      }
    };
    fetchLeaderboard();
  }, []);

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

  if (loading && !leaderboardData.length) { // Show initial loading state
    return (
      <div className="relative min-h-screen bg-soda-black text-soda-white flex items-center justify-center">
        <div className="fixed inset-0 z-0"><Orb hue={300} forceHoverState={true} /></div>
        <p className="text-xl">Loading Leaderboard...</p>
      </div>
    );
  }

  return (
    <div className="relative min-h-screen bg-soda-black text-soda-white overflow-x-hidden pt-20">
      <div className="fixed inset-0 z-0">
        <Orb hue={300} forceHoverState={true} hoverIntensity={0.05} /> {/* Unique hue for Leaderboard */}
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

      <div className="relative z-20 container mx-auto px-4 sm:px-6 lg:px-8 py-12 md:py-16">
        <h1 className="text-3xl sm:text-4xl md:text-5xl font-bold mb-10 md:mb-12 text-soda-white text-center tracking-tight">
          Leaderboard
        </h1>

        {error && <p className="text-center text-red-400 mb-6 text-lg">{error}</p>}

        <div className="bg-soda-gray/70 backdrop-blur-xl p-4 sm:p-6 md:p-8 rounded-xl shadow-2xl w-full max-w-5xl mx-auto">
          {leaderboardData.length > 0 ? (
            <div className="overflow-x-auto">
              <table className="min-w-full table-auto text-left">
                <thead className="border-b border-soda-white/20">
                  <tr>
                    <th className="px-4 py-3 sm:px-6 sm:py-4 text-sm font-semibold text-soda-white/80 tracking-wider">Rank</th>
                    <th className="px-4 py-3 sm:px-6 sm:py-4 text-sm font-semibold text-soda-white/80 tracking-wider">Name</th>
                    <th className="px-4 py-3 sm:px-6 sm:py-4 text-sm font-semibold text-soda-white/80 tracking-wider">Identifier</th>
                    <th className="px-4 py-3 sm:px-6 sm:py-4 text-sm font-semibold text-soda-white/80 tracking-wider text-right">Points</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-soda-white/10">
                  {leaderboardData.map((user, index) => (
                    <tr key={user.identifier || index} className="hover:bg-soda-black/20 transition-colors duration-150">
                      <td className="px-4 py-3 sm:px-6 sm:py-4 whitespace-nowrap text-soda-white/90 font-medium">{index + 1}</td>
                      <td className="px-4 py-3 sm:px-6 sm:py-4 whitespace-nowrap">
                        <button
                          className="text-soda-blue hover:text-soda-red transition-colors duration-150 font-medium"
                          onClick={() => viewUserDetails(user.identifier)}
                        >
                          {user.name}
                        </button>
                      </td>
                      <td className="px-4 py-3 sm:px-6 sm:py-4 whitespace-nowrap text-soda-white/70">{user.identifier}</td>
                      <td className="px-4 py-3 sm:px-6 sm:py-4 whitespace-nowrap text-soda-white text-right font-semibold">{user.points}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          ) : (
            !loading && <p className="text-center text-soda-white/70 py-8">No leaderboard data available yet.</p>
          )}
        </div>

        {/* Modal for viewing user details */}
        {showModal && (
          <div className="fixed inset-0 bg-soda-black/80 backdrop-blur-sm flex items-center justify-center z-50 p-4 transition-opacity duration-300 ease-in-out">
            <div className="bg-soda-gray/90 backdrop-blur-xl rounded-xl shadow-2xl w-full max-w-3xl mx-auto max-h-[90vh] flex flex-col overflow-hidden border border-soda-white/10">
              <div className="p-5 sm:p-6 border-b border-soda-white/10 flex justify-between items-center">
                <h2 className="text-xl sm:text-2xl font-semibold text-soda-white">{selectedUser?.name || 'User Details'}</h2>
                <button onClick={closeModal} className="text-soda-white/70 hover:text-soda-white transition-colors">
                  <FaTimes className="h-6 w-6" />
                </button>
              </div>

              <div className="flex-1 h-0 overflow-y-auto p-5 sm:p-6 space-y-4">
                {loadingUser ? (
                  <div className="text-soda-white/80 text-center py-10">Loading user details...</div>
                ) : modalError ? (
                  <div className="text-red-400 text-center py-10">{modalError}</div>
                ) : selectedUser && (
                  <>
                    <div className="grid grid-cols-1 sm:grid-cols-2 gap-x-6 gap-y-3 text-sm">
                      <p><strong className="text-soda-white/70">UUID:</strong> {selectedUser.uuid}</p>
                      <p><strong className="text-soda-white/70">Email:</strong> {selectedUserEmail}</p>
                      <p><strong className="text-soda-white/70">Academic Standing:</strong> {selectedUser.academic_standing}</p>
                      <p><strong className="text-soda-white/70">Major:</strong> {selectedUser.major}</p>
                    </div>
                    <h3 className="text-lg sm:text-xl font-semibold text-soda-white pt-4 mt-4 border-t border-soda-white/10">Points History</h3>
                    {selectedUser.points_earned && selectedUser.points_earned.length > 0 ? (
                      <div className="overflow-x-auto -mx-5 sm:-mx-6 rounded-b-xl">
                      <table className="min-w-full table-auto">
                          <thead className="bg-soda-black/30">
                            <tr>
                              <th className="px-4 py-2 sm:px-5 text-xs font-medium text-soda-white/70 uppercase tracking-wider text-left">Event</th>
                              <th className="px-4 py-2 sm:px-5 text-xs font-medium text-soda-white/70 uppercase tracking-wider text-left">Points</th>
                              <th className="px-4 py-2 sm:px-5 text-xs font-medium text-soda-white/70 uppercase tracking-wider text-left hidden md:table-cell">Awarded By</th>
                              <th className="px-4 py-2 sm:px-5 text-xs font-medium text-soda-white/70 uppercase tracking-wider text-left hidden lg:table-cell">Date</th>
                              <th className="px-4 py-2 sm:px-5 text-xs font-medium text-soda-white/70 uppercase tracking-wider text-center">Action</th>
                          </tr>
                        </thead>
                          <tbody className="divide-y divide-soda-white/10">
                            {selectedUser.points_earned.map((point) => (
                              <tr key={point.event + point.timestamp} className="hover:bg-soda-black/20 transition-colors">
                                <td className="px-4 py-3 sm:px-5 whitespace-nowrap text-soda-white/90 text-sm">{point.event}</td>
                                <td className="px-4 py-3 sm:px-5 whitespace-nowrap text-soda-white/90 text-sm">{point.points}</td>
                                <td className="px-4 py-3 sm:px-5 whitespace-nowrap text-soda-white/80 text-sm hidden md:table-cell">{point.awarded_by_officer}</td>
                                <td className="px-4 py-3 sm:px-5 whitespace-nowrap text-soda-white/80 text-sm hidden lg:table-cell">{new Date(point.timestamp).toLocaleDateString()}</td>
                                <td className="px-4 py-3 sm:px-5 whitespace-nowrap text-center">
                                <button
                                    onClick={() => handleDeleteClick(point)} // Pass the whole point object
                                  disabled={deleteLoading}
                                    className="text-red-500 hover:text-red-400 disabled:opacity-50 transition-colors p-1 rounded-md"
                                    title="Delete Points for this Event"
                                >
                                    <FaTrashAlt className="h-4 w-4" />
                                </button>
                              </td>
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    </div>
                    ) : (
                      <p className="text-soda-white/70 text-sm text-center py-5">No points history found for this user.</p>
                    )}
                  </>
                )}
              </div>
            </div>
          </div>
        )}

        {showConfirmModal && (
          <div className="fixed inset-0 bg-soda-black/80 backdrop-blur-sm flex items-center justify-center z-[60] p-4">
            <div className="bg-soda-gray/90 backdrop-blur-xl rounded-xl shadow-2xl w-full max-w-md mx-auto p-6 border border-soda-white/10">
              <h3 className="text-xl font-semibold mb-4 text-soda-white">Confirm Deletion</h3>
              <p className="text-soda-white/80 mb-6">
                Are you sure you want to delete points for the event "{pointToDelete?.event}"? This action cannot be undone.
              </p>
              <div className="flex justify-end space-x-3">
                <button
                  onClick={handleCancelDelete}
                  className="px-4 py-2 bg-soda-black/50 text-soda-white/80 rounded-md hover:bg-soda-black/70 transition-colors border border-soda-white/20"
                >
                  Cancel
                </button>
                <StarBorder
                  onClick={handleConfirmedDelete}
                  disabled={deleteLoading}
                  color="#FF3B30" // soda-red for delete confirmation
                  speed="4s"
                  className="shrink-0"
                  as="button" // Ensure it's a button type if not default
                >
                  {deleteLoading ? 'Deleting...' : 'Delete'}
                </StarBorder>
              </div>
            </div>
          </div>
        )}
      </div>
    </div>
  );
};

export default LeaderboardPage;
