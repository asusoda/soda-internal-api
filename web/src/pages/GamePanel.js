import React, { useState, useEffect } from 'react';
import apiClient from '../components/utils/axios';
import useAuthToken from '../hooks/userAuth';
import useOrgNavigation from '../hooks/useOrgNavigation';
import { useAuth } from '../components/auth/AuthContext';
import OrganizationNavbar from '../components/shared/OrganizationNavbar';
import { FaGamepad, FaPlay, FaStop, FaCog, FaUsers, FaTrophy } from 'react-icons/fa';

const GamePanel = () => {
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

  const [games, setGames] = useState([]);
  const [activeGame, setActiveGame] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

  useEffect(() => {
    fetchGames();
  }, []);

  const fetchGames = async () => {
    try {
      setLoading(true);
      const response = await apiClient.get('/games/list');
      setGames(response.data.games || []);
      setActiveGame(response.data.active_game || null);
    } catch (error) {
      setError('Failed to fetch games');
      console.error('Error fetching games:', error);
    } finally {
      setLoading(false);
    }
  };

  const startGame = async (gameId) => {
    try {
      setLoading(true);
      await apiClient.post(`/games/${gameId}/start`);
      await fetchGames(); // Refresh games list
      setError('');
      } catch (error) {
      setError('Failed to start game');
      console.error('Error starting game:', error);
    } finally {
      setLoading(false);
    }
  };

  const stopGame = async (gameId) => {
    try {
      setLoading(true);
      await apiClient.post(`/games/${gameId}/stop`);
      await fetchGames(); // Refresh games list
      setError('');
      } catch (error) {
      setError('Failed to stop game');
      console.error('Error stopping game:', error);
    } finally {
      setLoading(false);
    }
  };

    return (
    <OrganizationNavbar>
      <div className="max-w-6xl mx-auto">
        <div className="text-center mb-8">
          <h1 className="text-3xl font-bold mb-2">Game Panel</h1>
          <p className="text-gray-400">Manage game settings and configurations</p>
        </div>

        {error && (
          <div className="mb-6 p-4 bg-red-900/50 border border-red-500 rounded-md text-red-200">
            {error}
          </div>
        )}

        {/* Active Game Status */}
        {activeGame && (
          <div className="mb-8 bg-green-900/50 backdrop-blur-sm rounded-xl border border-green-700 p-6">
            <h2 className="text-xl font-semibold mb-4 flex items-center">
              <FaPlay className="mr-2 text-green-400" />
              Active Game
            </h2>
            <div className="flex items-center justify-between">
              <div>
                <div className="text-white font-medium text-lg">{activeGame.name}</div>
                <div className="text-sm text-gray-400">Started: {new Date(activeGame.start_time).toLocaleString()}</div>
                <div className="text-sm text-gray-400">Players: {activeGame.player_count || 0}</div>
              </div>
        <button
                onClick={() => stopGame(activeGame.id)}
                disabled={loading}
                className="px-4 py-2 bg-red-600 hover:bg-red-700 disabled:bg-gray-600 text-white rounded-md transition-colors"
      >
                Stop Game
      </button>
            </div>
      </div>
        )}

        {/* Available Games */}
        <div className="bg-gray-900/50 backdrop-blur-sm rounded-xl border border-gray-700 p-6">
          <h2 className="text-xl font-semibold mb-4 flex items-center">
            <FaGamepad className="mr-2 text-blue-400" />
            Available Games
          </h2>
          
          {loading ? (
            <div className="flex items-center justify-center py-12">
              <div className="text-center">
                <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-blue-500 mx-auto mb-4"></div>
                <p className="text-gray-400">Loading games...</p>
              </div>
            </div>
          ) : games.length === 0 ? (
            <div className="text-center py-12">
              <p className="text-gray-400">No games available</p>
            </div>
          ) : (
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
              {games.map((game) => (
                <div key={game.id} className="bg-gray-800 rounded-lg p-6 border border-gray-700">
                  <div className="flex items-center justify-between mb-4">
                    <h3 className="text-lg font-semibold text-white">{game.name}</h3>
                    <span className={`px-2 py-1 rounded text-xs ${
                      game.status === 'active' ? 'bg-green-600 text-white' :
                      game.status === 'inactive' ? 'bg-gray-600 text-gray-300' :
                      'bg-yellow-600 text-white'
                    }`}>
                      {game.status}
                    </span>
                  </div>
                  
                  <p className="text-gray-400 text-sm mb-4">{game.description}</p>
                  
                  <div className="space-y-2 mb-4">
                    <div className="flex items-center text-sm">
                      <FaUsers className="mr-2 text-gray-400" />
                      <span className="text-gray-300">Max Players: {game.max_players}</span>
                    </div>
                    <div className="flex items-center text-sm">
                      <FaTrophy className="mr-2 text-gray-400" />
                      <span className="text-gray-300">Points: {game.points}</span>
                    </div>
                  </div>
                  
                  <button
                    onClick={() => startGame(game.id)}
                    disabled={loading || game.status === 'active'}
                    className="w-full px-4 py-2 bg-blue-600 hover:bg-blue-700 disabled:bg-gray-600 text-white rounded-md transition-colors"
                  >
                    {game.status === 'active' ? 'Game Active' : 'Start Game'}
                  </button>
                </div>
              ))}
            </div>
          )}
        </div>

        {/* Game Settings */}
        <div className="mt-8 bg-gray-900/50 backdrop-blur-sm rounded-xl border border-gray-700 p-6">
          <h2 className="text-xl font-semibold mb-4 flex items-center">
            <FaCog className="mr-2 text-purple-400" />
            Game Settings
          </h2>
          
          <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
            <div className="bg-gray-800 rounded-lg p-4">
              <h3 className="text-lg font-medium text-white mb-2">General Settings</h3>
              <div className="space-y-2 text-sm text-gray-300">
                <div>Auto-start games: Enabled</div>
                <div>Points multiplier: 1.0x</div>
                <div>Game timeout: 30 minutes</div>
              </div>
            </div>
            
            <div className="bg-gray-800 rounded-lg p-4">
              <h3 className="text-lg font-medium text-white mb-2">Discord Integration</h3>
              <div className="space-y-2 text-sm text-gray-300">
                <div>Bot commands: Enabled</div>
                <div>Role permissions: Active</div>
                <div>Channel notifications: On</div>
              </div>
            </div>
          </div>
        </div>
      </div>
    </OrganizationNavbar>
    );
};

export default GamePanel;
