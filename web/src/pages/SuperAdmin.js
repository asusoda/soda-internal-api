import React, { useState, useEffect } from 'react';
import { useAuth } from '../components/auth/AuthContext';
import { useNavigate } from 'react-router-dom';
import ThemedLoading from '../components/ui/ThemedLoading';
import Orb from '../components/ui/Orb';
import OrganizationCard from '../components/ui/OrganizationCard';
import { toast } from 'react-toastify';

const SuperAdmin = () => {
  const { getApiClient, isSuperAdmin, loading, selectOrganization, currentOrg } = useAuth();
  const [dashboardData, setDashboardData] = useState(null);
  const [dashboardLoading, setDashboardLoading] = useState(true);
  const [error, setError] = useState(null);
  const [roles, setRoles] = useState({});
  const [loadingRoles, setLoadingRoles] = useState({});
  const [configuringOrg, setConfiguringOrg] = useState(null);
  const [showRoleModal, setShowRoleModal] = useState(false);
  const [selectedRoleId, setSelectedRoleId] = useState('');
  const [updatingRole, setUpdatingRole] = useState(false);
  const [updatingPrefix, setUpdatingPrefix] = useState({});
  const [showCalendarModal, setShowCalendarModal] = useState(false);
  const [calendarSettings, setCalendarSettings] = useState({
    notion_database_id: '',
    calendar_sync_enabled: false,
    google_calendar_id: ''
  });
  const [updatingCalendar, setUpdatingCalendar] = useState(false);
  const [ocpSyncEnabled, setOcpSyncEnabled] = useState(false);
  const [updatingOcpSync, setUpdatingOcpSync] = useState(false);
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

  const fetchGuildRoles = async (guildId) => {
    if (roles[guildId]) return roles[guildId]; // Return cached roles
    
    try {
      setLoadingRoles(prev => ({ ...prev, [guildId]: true }));
      const client = getApiClient();
      const response = await client.get(`/api/superadmin/guild_roles/${guildId}`);
      const newRoles = { ...roles, [guildId]: response.data.roles };
      setRoles(newRoles);
      return response.data.roles;
    } catch (error) {
      console.error('Error fetching guild roles:', error);
      setError('Failed to load roles for guild: ' + error.message);
      return [];
    } finally {
      setLoadingRoles(prev => ({ ...prev, [guildId]: false }));
    }
  };

  const openRoleConfig = async (org) => {
    setConfiguringOrg(org);
    setSelectedRoleId(org.officer_role_id || '');
    await fetchGuildRoles(org.guild_id);
    setShowRoleModal(true);
  };

  const openCalendarConfig = async (org) => {
    setConfiguringOrg(org);
    setCalendarSettings({
      notion_database_id: org.notion_database_id || '',
      calendar_sync_enabled: org.calendar_sync_enabled || false,
      google_calendar_id: org.google_calendar_id || ''
    });
    setOcpSyncEnabled(org.ocp_sync_enabled || false);
    setShowCalendarModal(true);
  };

  const updateOfficerRole = async () => {
    if (!configuringOrg) return;
    
    try {
      setUpdatingRole(true);
      const client = getApiClient();
      await client.put(`/api/superadmin/update_officer_role/${configuringOrg.id}`, {
        officer_role_id: selectedRoleId || null
      });
      
      // Refresh dashboard data to get updated organization info
      await fetchDashboardData();
      setShowRoleModal(false);
      setConfiguringOrg(null);
      setSelectedRoleId('');
    } catch (error) {
      console.error('Error updating officer role:', error);
      setError('Failed to update officer role: ' + error.message);
    } finally {
      setUpdatingRole(false);
    }
  };

  const updateCalendarSettings = async () => {
    if (!configuringOrg) return;
    
    try {
      setUpdatingCalendar(true);
      const client = getApiClient();
      await client.put(`/api/organizations/${configuringOrg.id}/calendar`, calendarSettings);
      
      // Refresh dashboard data to get updated organization info
      await fetchDashboardData();
      setShowCalendarModal(false);
      setConfiguringOrg(null);
      setCalendarSettings({
        notion_database_id: '',
        calendar_sync_enabled: false,
        google_calendar_id: ''
      });
      toast.success('Calendar settings updated successfully');
    } catch (error) {
      console.error('Error updating calendar settings:', error);
      setError('Failed to update calendar settings: ' + error.message);
    } finally {
      setUpdatingCalendar(false);
    }
  };

  const updateOcpSync = async (enabled) => {
    if (!configuringOrg) return;
    try {
      setUpdatingOcpSync(true);
      const client = getApiClient();
      await client.put(`/api/organizations/${configuringOrg.id}/ocp-sync`, { ocp_sync_enabled: enabled });
      setOcpSyncEnabled(enabled);
      await fetchDashboardData();
      toast.success(`OCP sync ${enabled ? 'enabled' : 'disabled'} successfully`);
    } catch (error) {
      console.error('Error updating OCP sync:', error);
      setError('Failed to update OCP sync: ' + error.message);
    } finally {
      setUpdatingOcpSync(false);
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

  const updateOrganizationPrefix = async (orgId, newPrefix) => {
    try {
      setUpdatingPrefix(prev => ({ ...prev, [orgId]: true }));
      const client = getApiClient();
      await client.put(`/api/organizations/${orgId}/settings`, {
        prefix: newPrefix
      });
      
      // Refresh dashboard data to get updated organization info
      await fetchDashboardData();
      
      // Find the updated organization from the refreshed data
      const updatedOrg = dashboardData?.officer_orgs?.find(org => org.id === orgId) || 
                        dashboardData?.existing_orgs?.find(org => org.id === orgId);
      
      if (updatedOrg) {
        // Update the organization with new prefix
        const updatedOrgWithNewPrefix = { ...updatedOrg, prefix: newPrefix };
        
        // Update the current organization if it's the one being edited
        if (currentOrg && currentOrg.id === orgId) {
          selectOrganization(updatedOrgWithNewPrefix);
          
          // Show success message
          toast.success(`Organization prefix updated to /${newPrefix}`);
          
          // Redirect to the organization with the new prefix
          navigate(`/${newPrefix}/dashboard`);
        } else {
          // Show success message for other organizations
          toast.success(`Organization prefix updated to /${newPrefix}`);
        }
      }
    } catch (error) {
      console.error('Error updating organization prefix:', error);
      throw new Error('Failed to update prefix: ' + error.message);
    } finally {
      setUpdatingPrefix(prev => ({ ...prev, [orgId]: false }));
    }
  };

  const validatePrefix = (prefix) => {
    if (!prefix || prefix.trim() === '') {
      return 'Prefix cannot be empty';
    }
    if (prefix.length < 2) {
      return 'Prefix must be at least 2 characters';
    }
    if (prefix.length > 20) {
      return 'Prefix must be 20 characters or less';
    }
    if (!/^[a-z0-9_-]+$/.test(prefix)) {
      return 'Prefix can only contain lowercase letters, numbers, hyphens, and underscores';
    }
    return null;
  };

  if (loading || dashboardLoading) {
    return <ThemedLoading message="Loading SuperAdmin Dashboard..." />;
  }

  if (!isSuperAdmin) {
    return <ThemedLoading message="Checking SuperAdmin permissions..." />; // Will redirect via useEffect
  }

  if (error) {
    return (
      <div className="relative min-h-screen bg-black text-white overflow-hidden flex items-center justify-center">
        {/* Background Effects */}
        <div className="absolute inset-0">
          <Orb hue={300} forceHoverState={true} hoverIntensity={0.1} />
        </div>
        
        {/* Error Content */}
        <div className="relative z-10 text-center">
          <div className="bg-red-900/50 backdrop-blur-sm rounded-xl border border-red-500/50 p-8 max-w-md">
            <h2 className="text-2xl font-bold text-red-400 mb-4">Error</h2>
            <p className="text-red-300">{error}</p>
            <button
              onClick={() => window.location.reload()}
              className="mt-4 px-4 py-2 bg-red-600 hover:bg-red-700 rounded-md text-sm font-medium transition-colors"
            >
              Retry
            </button>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="relative min-h-screen bg-black text-white overflow-hidden">
      {/* Background Effects */}
      <div className="absolute inset-0">
        <Orb hue={300} forceHoverState={true} hoverIntensity={0.1} />
      </div>

      {/* Main Content */}
      <div className="relative z-10 container mx-auto px-4 py-8">
        <div className="flex items-center justify-between mb-12">
          <div>
            <h1 className="text-4xl font-bold text-white mb-2">SuperAdmin Dashboard</h1>
            <p className="text-gray-400 text-lg">Manage all organizations and system settings</p>
          </div>
          <button
            onClick={() => navigate('/select-organization')}
            className="px-6 py-3 bg-gray-700/50 hover:bg-gray-600/50 backdrop-blur-sm rounded-lg text-sm font-medium transition-all duration-200 border border-gray-600/50 hover:shadow-lg hover:scale-[1.02] active:scale-[0.98]"
          >
            <div className="flex items-center space-x-2">
              <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M10 19l-7-7m0 0l7-7m-7 7h18" />
              </svg>
              <span>Back to Organizations</span>
            </div>
          </button>
        </div>

        {/* Officer's Organizations Section */}
        {dashboardData?.officer_orgs?.length > 0 && (
          <div className="mb-12">
            <div className="flex items-center justify-between mb-6">
              <h2 className="text-2xl font-bold text-white">Your Organizations</h2>
              <div className="text-sm text-gray-400">
                {dashboardData.officer_orgs.length} organization{dashboardData.officer_orgs.length !== 1 ? 's' : ''}
              </div>
            </div>
            <div className="grid gap-6 md:grid-cols-2 lg:grid-cols-3">
              {dashboardData.officer_orgs.map((org) => (
                <OrganizationCard
                  key={org.id}
                  org={org}
                  variant="officer"
                  onViewDashboard={handleViewOrganization}
                  onConfigure={openRoleConfig}
                  onCalendarConfig={openCalendarConfig}
                  onPrefixUpdate={(newPrefix) => updateOrganizationPrefix(org.id, newPrefix)}
                  validatePrefix={validatePrefix}
                />
              ))}
            </div>
          </div>
        )}

        {/* Feature Cards Section */}
        <div className="mb-12">
          <div className="flex items-center justify-between mb-6">
            <h2 className="text-2xl font-bold text-white">Features</h2>
            <div className="text-sm text-gray-400">Quick access to tools</div>
          </div>
          <div className="grid gap-6 md:grid-cols-2 lg:grid-cols-4">
            {/* Config Card */}
            <div className="bg-gray-800/50 backdrop-blur-sm p-6 rounded-xl border border-gray-700/50 hover:border-gray-600/50 transition-all duration-200 hover:scale-[1.02] group">
              <div className="flex flex-col items-center text-center">
                <div className="w-16 h-16 bg-blue-900/50 rounded-xl flex items-center justify-center mb-4 group-hover:bg-blue-800/50 transition-colors">
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
            <div className="bg-gray-800/50 backdrop-blur-sm p-6 rounded-xl border border-gray-700/50 hover:border-gray-600/50 transition-all duration-200 hover:scale-[1.02] group">
              <div className="flex flex-col items-center text-center">
                <div className="w-16 h-16 bg-green-900/50 rounded-xl flex items-center justify-center mb-4 group-hover:bg-green-800/50 transition-colors">
                  <svg className="h-8 w-8 text-green-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M16 8v8m-4-5v5m-4-2v2m-2 4h12a2 2 0 002-2V6a2 2 0 00-2-2H6a2 2 0 00-2 2v12a2 2 0 002 2z" />
                  </svg>
                </div>
                <h3 className="text-lg font-semibold text-white mb-2">Leaderboard</h3>
                <p className="text-gray-400 text-sm">View and manage member rankings and achievements</p>
              </div>
            </div>

            {/* Marketing Card */}
            <div className="bg-gray-800/50 backdrop-blur-sm p-6 rounded-xl border border-gray-700/50 hover:border-gray-600/50 transition-all duration-200 hover:scale-[1.02] group">
              <div className="flex flex-col items-center text-center">
                <div className="w-16 h-16 bg-purple-900/50 rounded-xl flex items-center justify-center mb-4 group-hover:bg-purple-800/50 transition-colors">
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
            <div className="bg-gray-800/50 backdrop-blur-sm p-6 rounded-xl border border-gray-700/50 hover:border-gray-600/50 transition-all duration-200 hover:scale-[1.02] group">
              <div className="flex flex-col items-center text-center">
                <div className="w-16 h-16 bg-red-900/50 rounded-xl flex items-center justify-center mb-4 group-hover:bg-red-800/50 transition-colors">
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

        {/* Available Discord Servers */}
        <div className="mb-12">
          <div className="flex items-center justify-between mb-6">
            <h2 className="text-2xl font-bold text-white">Available Discord Servers</h2>
            <div className="text-sm text-gray-400">
              {dashboardData?.available_guilds?.length || 0} server{dashboardData?.available_guilds?.length !== 1 ? 's' : ''} available
            </div>
          </div>
          {dashboardData?.available_guilds?.length > 0 ? (
            <div className="grid gap-6 md:grid-cols-2 lg:grid-cols-3">
              {dashboardData.available_guilds.map((guild) => (
                <div
                  key={guild.id}
                  className="bg-gray-800/50 backdrop-blur-sm p-6 rounded-xl border border-gray-700/50 hover:border-gray-600/50 transition-all duration-200"
                >
                  <div className="flex items-center space-x-4 mb-4">
                    {guild.icon?.url && (
                      <img
                        src={guild.icon.url}
                        alt={`${guild.name} icon`}
                        className="w-12 h-12 rounded-xl border-2 border-gray-600/50"
                      />
                    )}
                    <div className="flex-1">
                      <h3 className="text-lg font-semibold text-white mb-1">{guild.name}</h3>
                      <p className="text-sm text-gray-400 font-mono">ID: {String(guild.id)}</p>
                    </div>
                  </div>
                  <button
                    onClick={() => addOrganization(guild.id)}
                    className="w-full px-4 py-3 bg-green-600/50 hover:bg-green-700/50 backdrop-blur-sm rounded-lg text-sm font-medium transition-all duration-200 border border-green-500/50 hover:shadow-lg hover:scale-[1.02] active:scale-[0.98]"
                  >
                    <div className="flex items-center justify-center space-x-2">
                      <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 6v6m0 0v6m0-6h6m-6 0H6" />
                      </svg>
                      <span>Add Organization</span>
                    </div>
                  </button>
                </div>
              ))}
            </div>
          ) : (
            <div className="text-center py-12">
              <div className="w-16 h-16 bg-gray-700/50 rounded-xl flex items-center justify-center mx-auto mb-4">
                <svg className="h-8 w-8 text-gray-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M20 13V6a2 2 0 00-2-2H6a2 2 0 00-2 2v7m16 0v5a2 2 0 01-2 2H6a2 2 0 01-2-2v-5m16 0h-2.586a1 1 0 00-.707.293l-2.414 2.414a1 1 0 01-.707.293h-3.172a1 1 0 01-.707-.293l-2.414-2.414A1 1 0 006.586 13H4" />
                </svg>
              </div>
              <p className="text-gray-400 text-lg">No new servers available to add</p>
              <p className="text-gray-500 text-sm mt-2">All available Discord servers have been added</p>
            </div>
          )}
        </div>

        {/* Existing Organizations */}
        <div>
          <div className="flex items-center justify-between mb-6">
            <h2 className="text-2xl font-bold text-white">Existing Organizations</h2>
            <div className="text-sm text-gray-400">
              {dashboardData?.existing_orgs?.length || 0} organization{dashboardData?.existing_orgs?.length !== 1 ? 's' : ''} managed
            </div>
          </div>
          {dashboardData?.existing_orgs?.length > 0 ? (
            <div className="grid gap-6 md:grid-cols-2 lg:grid-cols-3">
              {dashboardData.existing_orgs.map((org) => (
                <OrganizationCard
                  key={org.id}
                  org={org}
                  variant="existing"
                  onViewDashboard={handleViewOrganization}
                  onConfigure={openRoleConfig}
                  onCalendarConfig={openCalendarConfig}
                  onRemove={removeOrganization}
                  onPrefixUpdate={(newPrefix) => updateOrganizationPrefix(org.id, newPrefix)}
                  validatePrefix={validatePrefix}
                  showRemove={true}
                />
              ))}
            </div>
          ) : (
            <div className="text-center py-12">
              <div className="w-16 h-16 bg-gray-700/50 rounded-xl flex items-center justify-center mx-auto mb-4">
                <svg className="h-8 w-8 text-gray-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 21V5a2 2 0 00-2-2H7a2 2 0 00-2 2v16m14 0h2m-2 0h-5m-9 0H3m2 0h5M9 7h1m-1 4h1m4-4h1m-1 4h1m-5 10v-5a1 1 0 011-1h2a1 1 0 011 1v5m-4 0h4" />
                </svg>
              </div>
              <p className="text-gray-400 text-lg">No organizations found</p>
              <p className="text-gray-500 text-sm mt-2">Add Discord servers to get started</p>
            </div>
          )}
        </div>
      </div>

      {/* Role Configuration Modal */}
      {showRoleModal && configuringOrg && (
        <div className="fixed inset-0 bg-black/50 backdrop-blur-sm flex items-center justify-center z-50">
          <div className="bg-gray-800/90 backdrop-blur-sm rounded-xl border border-gray-600/50 p-6 max-w-md w-full mx-4">
            <h2 className="text-xl font-bold mb-4">Configure Officer Role</h2>
            <p className="text-gray-300 mb-4">
              Select the officer role for <span className="text-blue-400">{configuringOrg.name}</span>
            </p>
            
            {loadingRoles[configuringOrg.guild_id] ? (
              <div className="text-center py-4">
                <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-blue-400 mx-auto"></div>
                <p className="text-gray-400 mt-2">Loading roles...</p>
              </div>
            ) : (
              <div className="mb-4">
                <label className="block text-sm font-medium text-gray-300 mb-2">
                  Officer Role
                </label>
                <select
                  value={selectedRoleId}
                  onChange={(e) => setSelectedRoleId(e.target.value)}
                  className="w-full bg-gray-700/50 border border-gray-600/50 rounded-md px-3 py-2 text-white focus:outline-none focus:ring-2 focus:ring-blue-500"
                >
                  <option value="">No Officer Role</option>
                  {roles[configuringOrg.guild_id]?.map((role) => (
                    <option key={role.id} value={role.id}>
                      {role.name}
                    </option>
                  ))}
                </select>
              </div>
            )}
            
            <div className="flex space-x-3">
              <button
                onClick={() => {
                  setShowRoleModal(false);
                  setConfiguringOrg(null);
                  setSelectedRoleId('');
                }}
                className="flex-1 px-4 py-2 bg-gray-600/50 hover:bg-gray-500/50 backdrop-blur-sm rounded-md text-sm font-medium transition-colors border border-gray-500/50"
              >
                Cancel
              </button>
              <button
                onClick={updateOfficerRole}
                disabled={updatingRole}
                className="flex-1 px-4 py-2 bg-blue-600/50 hover:bg-blue-700/50 backdrop-blur-sm rounded-md text-sm font-medium transition-colors border border-blue-500/50 disabled:opacity-50 disabled:cursor-not-allowed"
              >
                {updatingRole ? 'Updating...' : 'Save Changes'}
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Calendar Configuration Modal */}
      {showCalendarModal && configuringOrg && (
        <div className="fixed inset-0 bg-black/50 backdrop-blur-sm flex items-center justify-center z-50">
          <div className="bg-gray-800/90 backdrop-blur-sm rounded-xl border border-gray-600/50 p-6 max-w-md w-full mx-4">
            <h2 className="text-xl font-bold mb-4">Configure Calendar & OCP Settings</h2>
            <p className="text-gray-300 mb-4">
              Configure calendar and OCP sync settings for <span className="text-blue-400">{configuringOrg.name}</span>
            </p>
            <div className="space-y-4">
              <div>
                <label className="block text-sm font-medium text-gray-300 mb-2">
                  Notion Database ID
                </label>
                <input
                  type="text"
                  value={calendarSettings.notion_database_id}
                  onChange={(e) => setCalendarSettings(prev => ({ ...prev, notion_database_id: e.target.value }))}
                  placeholder="Enter Notion database ID"
                  className="w-full bg-gray-700/50 border border-gray-600/50 rounded-md px-3 py-2 text-white focus:outline-none focus:ring-2 focus:ring-blue-500"
                />
              </div>
              
              <div>
                <label className="flex items-center space-x-2">
                  <input
                    type="checkbox"
                    checked={calendarSettings.calendar_sync_enabled}
                    onChange={(e) => setCalendarSettings(prev => ({ ...prev, calendar_sync_enabled: e.target.checked }))}
                    className="rounded border-gray-600/50 bg-gray-700/50 text-blue-500 focus:ring-blue-500"
                  />
                  <span className="text-sm font-medium text-gray-300">Enable Calendar Sync</span>
                </label>
              </div>
              
              <div>
                <label className="block text-sm font-medium text-gray-300 mb-2">
                  Google Calendar ID (Auto-generated)
                </label>
                <input
                  type="text"
                  value={calendarSettings.google_calendar_id}
                  onChange={(e) => setCalendarSettings(prev => ({ ...prev, google_calendar_id: e.target.value }))}
                  placeholder="Leave empty for auto-generation"
                  className="w-full bg-gray-700/50 border border-gray-600/50 rounded-md px-3 py-2 text-white focus:outline-none focus:ring-2 focus:ring-blue-500"
                />
              </div>
              <div>
                <label className="flex items-center space-x-2">
                  <input
                    type="checkbox"
                    checked={ocpSyncEnabled}
                    onChange={e => updateOcpSync(e.target.checked)}
                    disabled={updatingOcpSync}
                    className="rounded border-gray-600/50 bg-gray-700/50 text-green-500 focus:ring-green-500"
                  />
                  <span className="text-sm font-medium text-gray-300">Enable OCP Sync (Officer Points)</span>
                  {updatingOcpSync && <span className="ml-2 text-xs text-gray-400">Updating...</span>}
                </label>
              </div>
            </div>
            
            <div className="flex space-x-3 mt-6">
              <button
                onClick={() => {
                  setShowCalendarModal(false);
                  setConfiguringOrg(null);
                  setCalendarSettings({
                    notion_database_id: '',
                    calendar_sync_enabled: false,
                    google_calendar_id: ''
                  });
                  setOcpSyncEnabled(false);
                }}
                className="flex-1 px-4 py-2 bg-gray-600/50 hover:bg-gray-500/50 backdrop-blur-sm rounded-md text-sm font-medium transition-colors border border-gray-500/50"
              >
                Cancel
              </button>
              <button
                onClick={updateCalendarSettings}
                disabled={updatingCalendar}
                className="flex-1 px-4 py-2 bg-blue-600/50 hover:bg-blue-700/50 backdrop-blur-sm rounded-md text-sm font-medium transition-colors border border-blue-500/50 disabled:opacity-50 disabled:cursor-not-allowed"
              >
                {updatingCalendar ? 'Updating...' : 'Save Changes'}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};

export default SuperAdmin;