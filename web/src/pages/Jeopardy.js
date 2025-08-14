import React, { useState, useEffect } from 'react';
import apiClient from '../components/utils/axios';
import useAuthToken from '../hooks/userAuth';
import useOrgNavigation from '../hooks/useOrgNavigation';
import { useAuth } from '../components/auth/AuthContext';
import OrganizationNavbar from '../components/shared/OrganizationNavbar';
import { FaTrophy, FaPlay, FaUsers, FaCog } from 'react-icons/fa';

const Jeopardy = () => {
  useAuthToken();
  const { currentOrg } = useAuth();
  const { 
    goToDashboard,
    goToUsers, 
    goToLeaderboard,
    goToAddPoints,
    goToOCP,
    goToPanel 
  } = useOrgNavigation();

  const [jeopardyGames, setJeopardyGames] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

  useEffect(() => {
    fetchJeopardyGames();
  }, []);

  const fetchJeopardyGames = async () => {
    try {
      setLoading(true);
      const response = await apiClient.get('/jeopardy/games');
      setJeopardyGames(response.data.games || []);
        } catch (error) {
      setError('Failed to fetch Jeopardy games');
      console.error('Error fetching Jeopardy games:', error);
    } finally {
      setLoading(false);
    }
  };

  const startJeopardyGame = async (gameId) => {
    try {
      setLoading(true);
      await apiClient.post(`/jeopardy/${gameId}/start`);
      await fetchJeopardyGames(); // Refresh games list
      setError('');
        } catch (error) {
      setError('Failed to start Jeopardy game');
      console.error('Error starting Jeopardy game:', error);
    } finally {
      setLoading(false);
    }
  };

  return (
    <OrganizationNavbar>
      <div className="max-w-6xl mx-auto">
        <div className="text-center mb-8">
          <h1 className="text-3xl font-bold mb-2">Jeopardy</h1>
          <p className="text-gray-400">Host and manage Jeopardy game sessions</p>
        </div>

        {error && (
          <div className="mb-6 p-4 bg-red-900/50 border border-red-500 rounded-md text-red-200">
            {error}
          </div>
        )}

        {/* Jeopardy Games */}
        <div className="bg-gray-900/50 backdrop-blur-sm rounded-xl border border-gray-700 p-6">
          <h2 className="text-xl font-semibold mb-4 flex items-center">
            <FaTrophy className="mr-2 text-yellow-400" />
            Available Jeopardy Games
          </h2>
          
          {loading ? (
            <div className="flex items-center justify-center py-12">
              <div className="text-center">
                <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-blue-500 mx-auto mb-4"></div>
                <p className="text-gray-400">Loading Jeopardy games...</p>
              </div>
            </div>
          ) : jeopardyGames.length === 0 ? (
            <div className="text-center py-12">
              <p className="text-gray-400">No Jeopardy games available</p>
            </div>
          ) : (
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
              {jeopardyGames.map((game) => (
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
                      <span className="text-gray-300">Categories: {game.categories?.length || 0}</span>
                    </div>
                    <div className="flex items-center text-sm">
                      <FaTrophy className="mr-2 text-gray-400" />
                      <span className="text-gray-300">Questions: {game.question_count || 0}</span>
                    </div>
                  </div>
                  
                  <button
                    onClick={() => startJeopardyGame(game.id)}
                    disabled={loading || game.status === 'active'}
                    className="w-full px-4 py-2 bg-yellow-600 hover:bg-yellow-700 disabled:bg-gray-600 text-white rounded-md transition-colors"
                  >
                    {game.status === 'active' ? 'Game Active' : 'Start Game'}
                  </button>
                </div>
              ))}
            </div>
          )}
        </div>

        {/* Game Instructions */}
        <div className="mt-8 bg-gray-900/50 backdrop-blur-sm rounded-xl border border-gray-700 p-6">
          <h2 className="text-xl font-semibold mb-4 flex items-center">
            <FaCog className="mr-2 text-blue-400" />
            How to Play
          </h2>
          
          <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
            <div className="bg-gray-800 rounded-lg p-4">
              <h3 className="text-lg font-medium text-white mb-2">For Hosts</h3>
              <div className="space-y-2 text-sm text-gray-300">
                <div>• Start a Jeopardy game from the available options</div>
                <div>• Use Discord commands to control the game</div>
                <div>• Monitor player scores and progress</div>
                <div>• End the game when finished</div>
              </div>
            </div>
            
            <div className="bg-gray-800 rounded-lg p-4">
              <h3 className="text-lg font-medium text-white mb-2">For Players</h3>
              <div className="space-y-2 text-sm text-gray-300">
                <div>• Join the game using Discord commands</div>
                <div>• Answer questions in the designated channel</div>
                <div>• Earn points for correct answers</div>
                <div>• Compete for the highest score</div>
              </div>
            </div>
          </div>
        </div>
      </div>
    </OrganizationNavbar>
    );
};

export default Jeopardy;