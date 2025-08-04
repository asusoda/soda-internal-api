import React, { useState, useEffect } from 'react';
import { useAuth } from '../components/auth/AuthContext';
import { useNavigate } from 'react-router-dom';

const SuperAdmin = () => {
  const { getApiClient, isSuperAdmin, loading, selectOrganization } = useAuth();
  const [dashboardData, setDashboardData] = useState(null);
  const [dashboardLoading, setDashboardLoading] = useState(true);
  const [error, setError] = useState(null);
  const navigate = useNavigate();

  useEffect(() => {
    // Redirect if not superadmin (after loading is complete)
    if (!loading && !isSuperAdmin) {
      navigate('/select-organization');
      return;
    }

    // Fetch dashboard data if superadmin
    if (!loading && isSuperAdmin) {
      fetchDashboardData();
    }
  }, [isSuperAdmin, loading, navigate]);

  const fetchDashboardData = async () => {
    try {
      setDashboardLoading(true);
      const client = getApiClient();
      const response = await client.get('/api/superadmin/dashboard');
      setDashboardData(response.data);
    } catch (error) {
      console.error('Error fetching dashboard data:', error);
      setError('Failed to load dashboard data: ' + error.message);
    } finally {
      setDashboardLoading(false);
    }
  };

  const addOrganization = async (guildId) => {
    try {
      const client = getApiClient();
      // Ensure guildId is passed as a string to preserve precision
      await client.post(`/api/superadmin/add_org/${String(guildId)}`);
      // Refresh dashboard data
      await fetchDashboardData();
    } catch (error) {
      console.error('Error adding organization:', error);
      setError('Failed to add organization');
    }
  };

  const removeOrganization = async (orgId) => {
    if (!window.confirm('Are you sure you want to remove this organization?')) {
      return;
    }

    try {
      const client = getApiClient();
      await client.delete(`/api/superadmin/remove_org/${orgId}`);
      // Refresh dashboard data
      await fetchDashboardData();
    } catch (error) {
      console.error('Error removing organization:', error);
      setError('Failed to remove organization');
    }
  };

  const handleViewOrganization = (org) => {
    selectOrganization(org);
    navigate(`/${org.prefix}/dashboard`);
  };

  if (loading || dashboardLoading) {
    return (
      <div className="min-h-screen bg-gray-900 flex items-center justify-center">
        <div className="text-white">Loading SuperAdmin Dashboard...</div>
      </div>
    );
  }

  if (!isSuperAdmin) {
    return (
      <div className="min-h-screen bg-gray-900 flex items-center justify-center">
        <div className="text-white">Checking SuperAdmin permissions...</div>
      </div>
    ); // Will redirect via useEffect
  }

  if (error) {
    return (
      <div className="min-h-screen bg-gray-900 flex items-center justify-center">
        <div className="text-red-400">{error}</div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-gray-900 text-white">
      <div className="container mx-auto px-4 py-8">
        <div className="flex items-center justify-between mb-8">
          <h1 className="text-3xl font-bold">SuperAdmin Dashboard</h1>
          <button
            onClick={() => navigate('/select-organization')}
            className="px-4 py-2 bg-gray-700 hover:bg-gray-600 rounded-md text-sm font-medium transition-colors"
          >
            Back to Organizations
          </button>
        </div>

        {/* Officer's Organizations Section */}
        {dashboardData?.officer_orgs?.length > 0 && (
          <div className="mb-8">
            <h2 className="text-xl font-semibold mb-4">Your Organizations</h2>
            <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
              {dashboardData.officer_orgs.map((org) => (
                <div
                  key={org.id}
                  onClick={() => handleViewOrganization(org)}
                  className="bg-gray-800 p-4 rounded-lg border border-blue-600 cursor-pointer hover:bg-gray-750 transition-colors"
                >
                  <div className="flex items-center space-x-3 mb-3">
                    {org.icon_url && (
                      <img
                        src={org.icon_url}
                        alt={`${org.name} icon`}
                        className="w-10 h-10 rounded-full"
                      />
                    )}
                    <div className="flex-1">
                      <h3 className="font-medium text-blue-300">{org.name}</h3>
                      <p className="text-sm text-gray-400">/{org.prefix}</p>
                      <p className="text-xs text-gray-500">Guild ID: {String(org.guild_id)}</p>
                    </div>
                  </div>
                  <div className="text-right">
                    <span className="text-blue-400 text-sm">View Organization →</span>
                  </div>
                </div>
              ))}
            </div>
          </div>
        )}

        {/* Feature Cards Section */}
        <div className="mb-8">
          <h2 className="text-xl font-semibold mb-4">Features</h2>
          <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-4">
            {/* Config Card */}
            <div className="bg-gray-800 p-6 rounded-lg border border-gray-700 hover:border-gray-600 transition-colors">
              <div className="flex flex-col items-center text-center">
                <div className="w-16 h-16 bg-blue-900 rounded-full flex items-center justify-center mb-4">
                  <svg className="h-8 w-8 text-blue-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M10.325 4.317c.426-1.756 2.924-1.756 3.35 0a1.724 1.724 0 002.573 1.066c1.543-.94 3.31.826 2.37 2.37a1.724 1.724 0 001.065 2.572c1.756.426 1.756 2.924 0 3.35a1.724 1.724 0 00-1.066 2.573c.94 1.543-.826 3.31-2.37 2.37a1.724 1.724 0 00-2.572 1.065c-.426 1.756-2.924 1.756-3.35 0a1.724 1.724 0 00-2.573-1.066c-1.543.94-3.31-.826-2.37-2.37a1.724 1.724 0 00-1.065-2.572c-1.756-.426-1.756-2.924 0-3.35a1.724 1.724 0 001.066-2.573c-.94-1.543.826-3.31 2.37-2.37.996.608 2.296.07 2.572-1.065z" />
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 12a3 3 0 11-6 0 3 3 0 016 0z" />
                  </svg>
                </div>
                <h3 className="text-lg font-semibold text-white mb-2">Config</h3>
                <p className="text-gray-400 text-sm">Manage organization settings and preferences</p>
              </div>
            </div>

            {/* Leaderboard Card */}
            <div className="bg-gray-800 p-6 rounded-lg border border-gray-700 hover:border-gray-600 transition-colors">
              <div className="flex flex-col items-center text-center">
                <div className="w-16 h-16 bg-green-900 rounded-full flex items-center justify-center mb-4">
                  <svg className="h-8 w-8 text-green-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M16 8v8m-4-5v5m-4-2v2m-2 4h12a2 2 0 002-2V6a2 2 0 00-2-2H6a2 2 0 00-2 2v12a2 2 0 002 2z" />
                  </svg>
                </div>
                <h3 className="text-lg font-semibold text-white mb-2">Leaderboard</h3>
                <p className="text-gray-400 text-sm">View and manage member rankings and achievements</p>
              </div>
            </div>

            {/* Marketing Card */}
            <div className="bg-gray-800 p-6 rounded-lg border border-gray-700 hover:border-gray-600 transition-colors">
              <div className="flex flex-col items-center text-center">
                <div className="w-16 h-16 bg-purple-900 rounded-full flex items-center justify-center mb-4">
                  <svg className="h-8 w-8 text-purple-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M11 3.055A9.001 9.001 0 1020.945 13H11V3.055z" />
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M20.488 9H15V3.512A9.025 9.025 0 0120.488 9z" />
                  </svg>
                </div>
                <h3 className="text-lg font-semibold text-white mb-2">Marketing</h3>
                <p className="text-gray-400 text-sm">Upcoming marketing tools and campaigns</p>
              </div>
            </div>

            {/* Calendar Card */}
            <div className="bg-gray-800 p-6 rounded-lg border border-gray-700 hover:border-gray-600 transition-colors">
              <div className="flex flex-col items-center text-center">
                <div className="w-16 h-16 bg-red-900 rounded-full flex items-center justify-center mb-4">
                  <svg className="h-8 w-8 text-red-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M8 7V3m8 4V3m-9 8h10M5 21h14a2 2 0 002-2V7a2 2 0 00-2-2H5a2 2 0 00-2 2v12a2 2 0 002 2z" />
                  </svg>
                </div>
                <h3 className="text-lg font-semibold text-white mb-2">Calendar</h3>
                <p className="text-gray-400 text-sm">Schedule and manage events and activities</p>
              </div>
            </div>
          </div>
        </div>

        {/* Available Guilds to Add */}
        <div className="mb-8">
          <h2 className="text-xl font-semibold mb-4">Available Discord Servers</h2>
          {dashboardData?.available_guilds?.length > 0 ? (
            <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
              {dashboardData.available_guilds.map((guild) => (
                <div
                  key={guild.id}
                  className="bg-gray-800 p-4 rounded-lg border border-gray-700"
                >
                  <div className="flex items-center space-x-3 mb-3">
                    {guild.icon?.url && (
                      <img
                        src={guild.icon.url}
                        alt={`${guild.name} icon`}
                        className="w-10 h-10 rounded-full"
                      />
                    )}
                    <div>
                      <h3 className="font-medium">{guild.name}</h3>
                      <p className="text-sm text-gray-400">ID: {String(guild.id)}</p>
                    </div>
                  </div>
                  <button
                    onClick={() => addOrganization(guild.id)}
                    className="w-full px-3 py-2 bg-green-600 hover:bg-green-700 rounded-md text-sm font-medium transition-colors"
                  >
                    Add Organization
                  </button>
                </div>
              ))}
            </div>
          ) : (
            <p className="text-gray-400">No new servers available to add.</p>
          )}
        </div>

        {/* Existing Organizations */}
        <div>
          <h2 className="text-xl font-semibold mb-4">Existing Organizations</h2>
          {dashboardData?.existing_orgs?.length > 0 ? (
            <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
              {dashboardData.existing_orgs.map((org) => (
                <div
                  key={org.id}
                  className="bg-gray-800 p-4 rounded-lg border border-gray-700"
                >
                  <div className="flex items-center space-x-3 mb-3">
                    {org.icon_url && (
                      <img
                        src={org.icon_url}
                        alt={`${org.name} icon`}
                        className="w-10 h-10 rounded-full"
                      />
                    )}
                    <div className="flex-1">
                      <h3 className="font-medium">{org.name}</h3>
                      <p className="text-sm text-gray-400">/{org.prefix}</p>
                      <p className="text-xs text-gray-500">Guild ID: {String(org.guild_id)}</p>
                    </div>
                  </div>
                  <div className="flex space-x-2">
                    <button
                      onClick={() => handleViewOrganization(org)}
                      className="flex-1 px-3 py-2 bg-blue-600 hover:bg-blue-700 rounded-md text-sm font-medium transition-colors"
                    >
                      View Dashboard
                    </button>
                    <button
                      onClick={() => removeOrganization(org.id)}
                      className="px-3 py-2 bg-red-600 hover:bg-red-700 rounded-md text-sm font-medium transition-colors"
                    >
                      Remove
                    </button>
                  </div>
                </div>
              ))}
            </div>
          ) : (
            <p className="text-gray-400">No organizations found.</p>
          )}
        </div>
      </div>
    </div>
  );
};

export default SuperAdmin;