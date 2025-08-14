import React, { useState, useEffect } from 'react';
import apiClient from '../components/utils/axios';
import useAuthToken from '../hooks/userAuth';
import useOrgNavigation from '../hooks/useOrgNavigation';
import { useAuth } from '../components/auth/AuthContext';
import OrganizationNavbar from '../components/shared/OrganizationNavbar';
import { FaRobot, FaCog, FaPlay, FaStop, FaSync, FaInfoCircle } from 'react-icons/fa';

const BotControlPanel = () => {
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

  const [botStatus, setBotStatus] = useState('unknown');
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [logs, setLogs] = useState([]);

  useEffect(() => {
    fetchBotStatus();
  }, []);

  const fetchBotStatus = async () => {
    try {
      setLoading(true);
      const response = await apiClient.get('/bot/status');
      setBotStatus(response.data.status);
      setLogs(response.data.logs || []);
    } catch (error) {
      setError('Failed to fetch bot status');
      console.error('Error fetching bot status:', error);
    } finally {
      setLoading(false);
    }
  };

  const startBot = async () => {
    try {
      setLoading(true);
      await apiClient.post('/bot/start');
      setBotStatus('running');
      setError('');
    } catch (error) {
      setError('Failed to start bot');
      console.error('Error starting bot:', error);
    } finally {
      setLoading(false);
    }
  };

  const stopBot = async () => {
    try {
      setLoading(true);
      await apiClient.post('/bot/stop');
      setBotStatus('stopped');
      setError('');
    } catch (error) {
      setError('Failed to stop bot');
      console.error('Error stopping bot:', error);
    } finally {
      setLoading(false);
    }
  };

  const restartBot = async () => {
    try {
      setLoading(true);
      await apiClient.post('/bot/restart');
      setBotStatus('running');
      setError('');
    } catch (error) {
      setError('Failed to restart bot');
      console.error('Error restarting bot:', error);
    } finally {
      setLoading(false);
    }
  };

  return (
    <OrganizationNavbar>
      <div className="max-w-6xl mx-auto">
        <div className="text-center mb-8">
          <h1 className="text-3xl font-bold mb-2">Bot Control Panel</h1>
          <p className="text-gray-400">Manage Discord bot settings and configurations</p>
        </div>

        {error && (
          <div className="mb-6 p-4 bg-red-900/50 border border-red-500 rounded-md text-red-200">
            {error}
          </div>
        )}

        {/* Bot Status Card */}
        <div className="mb-8 bg-gray-900/50 backdrop-blur-sm rounded-xl border border-gray-700 p-6">
          <h2 className="text-xl font-semibold mb-4 flex items-center">
            <FaRobot className="mr-2 text-blue-400" />
            Bot Status
          </h2>
          
          <div className="flex items-center justify-between">
            <div className="flex items-center space-x-4">
              <div className={`w-4 h-4 rounded-full ${
                botStatus === 'running' ? 'bg-green-500' :
                botStatus === 'stopped' ? 'bg-red-500' :
                'bg-yellow-500'
              }`}></div>
              <div>
                <div className="text-white font-medium">
                  Status: {botStatus === 'running' ? 'Running' : 
                          botStatus === 'stopped' ? 'Stopped' : 
                          'Unknown'}
                </div>
                <div className="text-sm text-gray-400">
                  Last updated: {new Date().toLocaleTimeString()}
                </div>
              </div>
            </div>
            
            <button
              onClick={fetchBotStatus}
              disabled={loading}
              className="px-4 py-2 bg-gray-600 hover:bg-gray-700 disabled:bg-gray-600 text-white rounded-md transition-colors"
            >
              <FaSync className={`inline mr-2 ${loading ? 'animate-spin' : ''}`} />
              Refresh
            </button>
          </div>
        </div>

        {/* Control Buttons */}
        <div className="mb-8 bg-gray-900/50 backdrop-blur-sm rounded-xl border border-gray-700 p-6">
          <h2 className="text-xl font-semibold mb-4 flex items-center">
            <FaCog className="mr-2 text-purple-400" />
            Bot Controls
          </h2>
          
          <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
            <button
              onClick={startBot}
              disabled={loading || botStatus === 'running'}
              className="px-6 py-3 bg-green-600 hover:bg-green-700 disabled:bg-gray-600 text-white rounded-lg transition-colors flex items-center justify-center"
            >
              <FaPlay className="mr-2" />
              Start Bot
            </button>
            
            <button
              onClick={stopBot}
              disabled={loading || botStatus === 'stopped'}
              className="px-6 py-3 bg-red-600 hover:bg-red-700 disabled:bg-gray-600 text-white rounded-lg transition-colors flex items-center justify-center"
            >
              <FaStop className="mr-2" />
              Stop Bot
            </button>
            
            <button
              onClick={restartBot}
              disabled={loading}
              className="px-6 py-3 bg-yellow-600 hover:bg-yellow-700 disabled:bg-gray-600 text-white rounded-lg transition-colors flex items-center justify-center"
            >
              <FaSync className="mr-2" />
              Restart Bot
            </button>
          </div>
        </div>

        {/* Bot Logs */}
        <div className="bg-gray-900/50 backdrop-blur-sm rounded-xl border border-gray-700 p-6">
          <h2 className="text-xl font-semibold mb-4 flex items-center">
            <FaInfoCircle className="mr-2 text-green-400" />
            Bot Logs
          </h2>
          
          <div className="bg-gray-800 rounded-lg p-4 max-h-96 overflow-y-auto">
            {logs.length > 0 ? (
              <div className="space-y-2">
                {logs.map((log, index) => (
                  <div key={index} className="text-sm">
                    <span className="text-gray-400">[{log.timestamp}]</span>
                    <span className="text-white ml-2">{log.message}</span>
                  </div>
                ))}
              </div>
            ) : (
              <div className="text-gray-400 text-center py-8">
                No logs available
              </div>
            )}
          </div>
        </div>
      </div>
    </OrganizationNavbar>
  );
};

export default BotControlPanel;
