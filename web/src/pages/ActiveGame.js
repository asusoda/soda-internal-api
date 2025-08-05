import React, { useState, useEffect } from 'react';
import apiClient from '../components/utils/axios';
import useAuthToken from '../hooks/userAuth';
import useOrgNavigation from '../hooks/useOrgNavigation';
import { useAuth } from '../components/auth/AuthContext';
import OrganizationNavbar from '../components/shared/OrganizationNavbar';
import { FaPlay, FaStop, FaUsers, FaTrophy, FaClock, FaCog } from 'react-icons/fa';

const ActiveGame = () => {
  useAuthToken();
  const { currentOrg } = useAuth();
  const { 
    goToDashboard,
    goToUsers, 
    goToLeaderboard,
    goToAddPoints,
    goToOCP,
    goToJeopardy 
  } = useOrgNavigation();

  const [activeGame, setActiveGame] = useState(null);
  const [players, setPlayers] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

  useEffect(() => {
    fetchActiveGame();
    // Set up polling to refresh active game data
    const interval = setInterval(fetchActiveGame, 5000);
    return () => clearInterval(interval);
  }, []);

  const fetchActiveGame = async () => {
    try {
      setLoading(true);
      const response = await apiClient.get('/games/active');
      if (response.data.game) {
        setActiveGame(response.data.game);
        setPlayers(response.data.players || []);
      } else {
        setActiveGame(null);
        setPlayers([]);
      }
        } catch (error) {
      setError('Failed to fetch active game');
      console.error('Error fetching active game:', error);
    } finally {
      setLoading(false);
    }
  };

  const stopGame = async () => {
    try {
      setLoading(true);
      await apiClient.post('/games/stop');
      setActiveGame(null);
      setPlayers([]);
      setError('');
        } catch (error) {
      setError('Failed to stop game');
      console.error('Error stopping game:', error);
    } finally {
      setLoading(false);
    }
  };

  if (loading && !activeGame) {
    return (
      <OrganizationNavbar>
        <div className="flex items-center justify-center py-12">
          <div className="text-center">
            <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-blue-500 mx-auto mb-4"></div>
            <p className="text-gray-400">Loading active game...</p>
          </div>
        </div>
      </OrganizationNavbar>
    );
  }

  if (!activeGame) {
    return (
      <OrganizationNavbar>
        <div className="max-w-6xl mx-auto">
          <div className="text-center mb-8">
            <h1 className="text-3xl font-bold mb-2">Active Game</h1>
            <p className="text-gray-400">View and control currently running games</p>
          </div>

          <div className="bg-gray-900/50 backdrop-blur-sm rounded-xl border border-gray-700 p-12 text-center">
            <FaPlay className="text-6xl text-gray-600 mx-auto mb-4" />
            <h2 className="text-2xl font-semibold text-white mb-2">No Active Game</h2>
            <p className="text-gray-400 mb-6">There is currently no active game running.</p>
            <p className="text-sm text-gray-500">Start a game from the Game Panel to see it here.</p>
          </div>
        </div>
      </OrganizationNavbar>
    );
  }

  return (
    <OrganizationNavbar>
      <div className="max-w-6xl mx-auto">
        <div className="text-center mb-8">
          <h1 className="text-3xl font-bold mb-2">Active Game</h1>
          <p className="text-gray-400">View and control currently running games</p>
        </div>

        {error && (
          <div className="mb-6 p-4 bg-red-900/50 border border-red-500 rounded-md text-red-200">
            {error}
          </div>
        )}

        {/* Active Game Status */}
        <div className="mb-8 bg-green-900/50 backdrop-blur-sm rounded-xl border border-green-700 p-6">
          <div className="flex items-center justify-between mb-4">
            <h2 className="text-xl font-semibold flex items-center">
              <FaPlay className="mr-2 text-green-400" />
              {activeGame.name}
            </h2>
            <button
              onClick={stopGame}
              disabled={loading}
              className="px-4 py-2 bg-red-600 hover:bg-red-700 disabled:bg-gray-600 text-white rounded-md transition-colors"
            >
              Stop Game
            </button>
          </div>
          
          <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
            <div className="flex items-center">
              <FaClock className="mr-2 text-gray-400" />
              <div>
                <div className="text-white font-medium">Duration</div>
                <div className="text-sm text-gray-400">
                  {Math.floor((Date.now() - new Date(activeGame.start_time).getTime()) / 60000)} minutes
                </div>
              </div>
            </div>
            
            <div className="flex items-center">
              <FaUsers className="mr-2 text-gray-400" />
              <div>
                <div className="text-white font-medium">Players</div>
                <div className="text-sm text-gray-400">{players.length} active</div>
              </div>
            </div>
            
            <div className="flex items-center">
              <FaTrophy className="mr-2 text-gray-400" />
              <div>
                <div className="text-white font-medium">Status</div>
                <div className="text-sm text-green-400">Running</div>
              </div>
            </div>
          </div>
        </div>

        {/* Player List */}
        <div className="mb-8 bg-gray-900/50 backdrop-blur-sm rounded-xl border border-gray-700 p-6">
          <h2 className="text-xl font-semibold mb-4 flex items-center">
            <FaUsers className="mr-2 text-blue-400" />
            Active Players
          </h2>
          
          {players.length === 0 ? (
            <div className="text-center py-8">
              <p className="text-gray-400">No players currently in the game</p>
            </div>
          ) : (
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
              {players.map((player, index) => (
                <div key={player.id || index} className="bg-gray-800 rounded-lg p-4 border border-gray-700">
                  <div className="flex items-center justify-between">
                    <div>
                      <div className="text-white font-medium">{player.name}</div>
                      <div className="text-sm text-gray-400">{player.email}</div>
                    </div>
                    <div className="text-right">
                      <div className="text-green-400 font-bold">{player.score || 0}</div>
                      <div className="text-xs text-gray-500">points</div>
                    </div>
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>

        {/* Game Statistics */}
        <div className="bg-gray-900/50 backdrop-blur-sm rounded-xl border border-gray-700 p-6">
          <h2 className="text-xl font-semibold mb-4 flex items-center">
            <FaCog className="mr-2 text-purple-400" />
            Game Statistics
          </h2>
          
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
            <div className="bg-gray-800 rounded-lg p-4 text-center">
              <div className="text-2xl font-bold text-white">{players.length}</div>
              <div className="text-sm text-gray-400">Total Players</div>
            </div>
            
            <div className="bg-gray-800 rounded-lg p-4 text-center">
              <div className="text-2xl font-bold text-green-400">
                {players.reduce((sum, player) => sum + (player.score || 0), 0)}
              </div>
              <div className="text-sm text-gray-400">Total Points</div>
            </div>
            
            <div className="bg-gray-800 rounded-lg p-4 text-center">
              <div className="text-2xl font-bold text-blue-400">
                {players.length > 0 ? Math.round(players.reduce((sum, player) => sum + (player.score || 0), 0) / players.length) : 0}
              </div>
              <div className="text-sm text-gray-400">Average Score</div>
            </div>
            
            <div className="bg-gray-800 rounded-lg p-4 text-center">
              <div className="text-2xl font-bold text-yellow-400">
                {Math.floor((Date.now() - new Date(activeGame.start_time).getTime()) / 60000)}
              </div>
              <div className="text-sm text-gray-400">Minutes Elapsed</div>
            </div>
             </div>
        </div>
      </div>
    </OrganizationNavbar>
    );
};

export default ActiveGame;