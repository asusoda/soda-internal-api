import React, { useState, useEffect, useCallback } from 'react';
import apiClient from '../components/utils/axios';

import useAuthToken from '../hooks/userAuth';
import useOrgNavigation from '../hooks/useOrgNavigation';
import { useAuth } from '../components/auth/AuthContext';
import OrganizationNavbar from '../components/shared/OrganizationNavbar';
import StarBorder from '../components/ui/StarBorder';
import {
    FaUsers, FaSignOutAlt, FaTachometerAlt, FaClipboardList, 
    FaCogs, FaRedo, FaSearchDollar, FaWrench, FaExclamationTriangle, FaSync, FaFlask, FaPlusCircle, FaTimes
} from 'react-icons/fa';

// (Line removed)

// Helper functions (can be outside any component if they don't use hooks or component state)
const formatDate = (dateString) => {
  if (!dateString) return 'N/A';
  try {
    return new Date(dateString).toLocaleDateString('en-US', { year: 'numeric', month: 'short', day: 'numeric' });
  } catch (e) {
    return dateString;
  }
};

const getEventTypeColor = (eventType) => {
  switch (eventType) {
    case 'GBM': return 'bg-soda-blue/20 text-soda-blue';
    case 'Special Event': return 'bg-soda-red/20 text-soda-red';
    case 'Workshop': return 'bg-green-500/20 text-green-400';
    case 'Social': return 'bg-yellow-500/20 text-yellow-400';
    case 'Special Contribution': return 'bg-purple-500/20 text-purple-400';
    default: return 'bg-soda-gray text-soda-white/70';
  }
};

// AddContributionModal Component (Moved outside OCPDetails, hooks before early return)
const AddContributionModal = ({ isOpen, onClose, onAdd }) => {
  // Hooks must be called unconditionally at the top level of the component
  const [selectedOfficers, setSelectedOfficers] = useState([]);
  const [customOfficerName, setCustomOfficerName] = useState('');
  const [availableOfficers, setAvailableOfficers] = useState([]);
  const [loadingOfficers, setLoadingOfficers] = useState(false);
  const [eventDescription, setEventDescription] = useState('');
  const [points, setPoints] = useState(1);
  const [role, setRole] = useState('');
  const [eventType, setEventType] = useState('Other');
  const [eventDate, setEventDate] = useState(new Date().toISOString().split('T')[0]);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [formError, setFormError] = useState('');

  // Fetch available officers when modal opens
  React.useEffect(() => {
    if (isOpen && availableOfficers.length === 0) {
      fetchAvailableOfficers();
    }
  }, [isOpen]);

  const fetchAvailableOfficers = async () => {
    setLoadingOfficers(true);
    try {
      const response = await apiClient.get('/api/ocp/officer-names');
      if (response.data.status === 'success') {
        setAvailableOfficers(response.data.officers);
      }
    } catch (error) {
      console.error('Error fetching officer names:', error);
    } finally {
      setLoadingOfficers(false);
    }
  };

  const handleOfficerSelect = (officer) => {
    if (!selectedOfficers.find(o => o.uuid === officer.uuid)) {
      setSelectedOfficers([...selectedOfficers, officer]);
    }
  };

  const handleRemoveOfficer = (officerToRemove) => {
    setSelectedOfficers(selectedOfficers.filter(o => o.uuid !== officerToRemove.uuid));
  };

  const handleAddCustomOfficer = () => {
    if (customOfficerName.trim() && !selectedOfficers.find(o => o.name === customOfficerName.trim())) {
      setSelectedOfficers([...selectedOfficers, { name: customOfficerName.trim(), uuid: 'custom_' + Date.now() }]);
      setCustomOfficerName('');
    }
  };

  if (!isOpen) return null; // Early return after hooks

  const handleSubmit = async (e) => {
    e.preventDefault();
    if (selectedOfficers.length === 0 || !eventDescription) {
        setFormError('At least one officer and event description are required.');
        return;
    }
    setIsSubmitting(true);
    setFormError('');
    
    const officerNames = selectedOfficers.map(officer => officer.name);
    const contributionData = {
        names: officerNames,
        event: eventDescription,
        points: parseInt(points, 10) || 1,
        role: role || undefined,
        event_type: eventType || undefined,
        timestamp: eventDate ? new Date(eventDate).toISOString() : undefined
    };
    const success = await onAdd(contributionData);
    setIsSubmitting(false);
    
    // Clear form only on success
    if (success) {
      setSelectedOfficers([]);
      setCustomOfficerName('');
      setEventDescription('');
      setPoints(1);
      setRole('');
      setEventType('Other');
      setEventDate(new Date().toISOString().split('T')[0]);
    }
  };

  return (
    <div className="fixed inset-0 bg-soda-black/80 backdrop-blur-md flex items-center justify-center z-50 p-4">
      <div className="bg-soda-gray/90 backdrop-blur-xl rounded-xl shadow-2xl w-full max-w-lg mx-auto max-h-[90vh] flex flex-col overflow-hidden border border-soda-white/10">
        <div className="p-5 border-b border-soda-white/10 flex justify-between items-center">
          <h2 className="text-xl font-semibold text-soda-white">Log New Contribution</h2>
          <button onClick={onClose} className="text-soda-white/70 hover:text-soda-white transition-colors">
            <FaTimes className="h-6 w-6" />
          </button>
        </div>
        <form onSubmit={handleSubmit} className="p-6 space-y-4 overflow-y-auto">
          {formError && <p className="text-red-400 text-sm">{formError}</p>}
          
          {/* Officer Selection Section */}
          <div>
            <label className="block text-sm font-medium text-soda-white/90 mb-2">Select Officers <span className="text-soda-red">*</span></label>
            
            {/* Available Officers Dropdown */}
            <div className="mb-3">
              <label htmlFor="existingOfficers" className="block text-xs text-soda-white/70 mb-1">Choose from existing officers:</label>
              {loadingOfficers ? (
                <p className="text-soda-white/60 text-sm">Loading officers...</p>
              ) : (
                <select 
                  id="existingOfficers" 
                  onChange={(e) => {
                    const selectedUuid = e.target.value;
                    if (selectedUuid) {
                      const officer = availableOfficers.find(o => o.uuid === selectedUuid);
                      if (officer) {
                        handleOfficerSelect(officer);
                        e.target.value = ''; // Reset dropdown
                      }
                    }
                  }}
                  className="w-full p-2.5 rounded-md bg-soda-black/50 border border-soda-white/20 text-soda-white focus:ring-soda-blue focus:border-soda-blue"
                >
                  <option value="">-- Select an existing officer --</option>
                  {availableOfficers.map((officer) => (
                    <option key={officer.uuid} value={officer.uuid}>
                      {officer.name}
                    </option>
                  ))}
                </select>
              )}
            </div>

            {/* Add Custom Officer */}
            <div className="mb-3">
              <label htmlFor="customOfficer" className="block text-xs text-soda-white/70 mb-1">Or add a new officer:</label>
              <div className="flex gap-2">
                <input 
                  type="text" 
                  id="customOfficer" 
                  value={customOfficerName} 
                  onChange={(e) => setCustomOfficerName(e.target.value)}
                  onKeyPress={(e) => e.key === 'Enter' && e.preventDefault()}
                  placeholder="Enter new officer name"
                  className="flex-1 p-2.5 rounded-md bg-soda-black/50 border border-soda-white/20 text-soda-white focus:ring-soda-blue focus:border-soda-blue" 
                />
                <button 
                  type="button" 
                  onClick={handleAddCustomOfficer}
                  disabled={!customOfficerName.trim()}
                  className="px-4 py-2.5 bg-soda-blue hover:bg-soda-blue/80 disabled:bg-soda-gray/50 disabled:text-soda-white/50 text-white rounded-md transition-colors"
                >
                  Add
                </button>
              </div>
            </div>

            {/* Selected Officers Display */}
            {selectedOfficers.length > 0 && (
              <div>
                <label className="block text-xs text-soda-white/70 mb-2">Selected officers ({selectedOfficers.length}):</label>
                <div className="flex flex-wrap gap-2">
                  {selectedOfficers.map((officer) => (
                    <div 
                      key={officer.uuid} 
                      className="flex items-center bg-soda-blue/20 text-soda-blue border border-soda-blue/30 rounded-md px-3 py-1 text-sm"
                    >
                      <span>{officer.name}</span>
                      <button 
                        type="button" 
                        onClick={() => handleRemoveOfficer(officer)}
                        className="ml-2 text-soda-blue hover:text-soda-red transition-colors"
                      >
                        <FaTimes className="h-3 w-3" />
                      </button>
                    </div>
                  ))}
                </div>
              </div>
            )}
          </div>
          <div>
            <label htmlFor="eventDescription" className="block text-sm font-medium text-soda-white/90 mb-1">Event Description <span className="text-soda-red">*</span></label>
            <input type="text" id="eventDescription" value={eventDescription} onChange={e => setEventDescription(e.target.value)} required className="w-full p-2.5 rounded-md bg-soda-black/50 border border-soda-white/20 text-soda-white focus:ring-soda-blue focus:border-soda-blue" />
          </div>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div>
              <label htmlFor="points" className="block text-sm font-medium text-soda-white/90 mb-1">Points</label>
              <input type="number" id="points" value={points} onChange={e => setPoints(Math.max(0, parseInt(e.target.value,10) || 0))} className="w-full p-2.5 rounded-md bg-soda-black/50 border border-soda-white/20 text-soda-white focus:ring-soda-blue focus:border-soda-blue" />
            </div>
            <div>
                <label htmlFor="eventType" className="block text-sm font-medium text-soda-white/90 mb-1">Event Type</label>
                <select id="eventType" value={eventType} onChange={e => setEventType(e.target.value)} className="w-full p-2.5 rounded-md bg-soda-black/50 border border-soda-white/20 text-soda-white focus:ring-soda-blue focus:border-soda-blue h-[46px]">
                    <option value="Other">Other</option>
                    <option value="GBM">GBM</option>
                    <option value="Special Event">Special Event</option>
                    <option value="Workshop">Workshop</option>
                    <option value="Social">Social</option>
                    <option value="Special Contribution">Special Contribution</option>
                </select>
            </div>
          </div>
          <div>
            <label htmlFor="role" className="block text-sm font-medium text-soda-white/90 mb-1">Role (Optional)</label>
            <input type="text" id="role" value={role} onChange={e => setRole(e.target.value)} className="w-full p-2.5 rounded-md bg-soda-black/50 border border-soda-white/20 text-soda-white focus:ring-soda-blue focus:border-soda-blue" />
          </div>
          <div>
            <label htmlFor="eventDate" className="block text-sm font-medium text-soda-white/90 mb-1">Event Date</label>
            <input 
              type="date" 
              id="eventDate" 
              value={eventDate} 
              onChange={e => setEventDate(e.target.value)} 
              className="w-full p-2.5 rounded-md bg-soda-black/50 border border-soda-white/20 text-soda-white focus:ring-soda-blue focus:border-soda-blue [color-scheme:dark]"
              style={{
                WebkitAppearance: 'none',
                MozAppearance: 'none',
                appearance: 'none'
              }}
            />
          </div>
          <div className="pt-2 flex justify-end">
            <StarBorder type="submit" color="#007AFF" disabled={isSubmitting} className="py-2.5">
              {isSubmitting ? 'Submitting...' : 'Log Contribution'}
            </StarBorder>
          </div>
        </form>
      </div>
    </div>
  );
};

// EventParticipantsModal Component (Moved outside OCPDetails)
const EventParticipantsModal = ({ isOpen, onClose, eventData }) => {
  if (!isOpen || !eventData) return null;

  return (
    <div className="fixed inset-0 bg-soda-black/80 backdrop-blur-md flex items-center justify-center z-50 p-4">
      <div className="bg-soda-gray/90 backdrop-blur-xl rounded-xl shadow-2xl w-full max-w-2xl mx-auto max-h-[90vh] flex flex-col overflow-hidden border border-soda-white/10">
        <div className="p-5 border-b border-soda-white/10 flex justify-between items-center">
          <h2 className="text-xl font-semibold text-soda-white">Event Participants: {eventData.eventName}</h2>
          <button onClick={onClose} className="text-soda-white/70 hover:text-soda-white transition-colors">
            <FaTimes className="h-6 w-6" />
          </button>
        </div>
        <div className="p-6 space-y-4 overflow-y-auto">
          <div className="grid grid-cols-2 gap-2 text-sm mb-4">
            <p><strong className="text-soda-white/70">Date:</strong> {formatDate(eventData.eventDate)}</p>
            <p><strong className="text-soda-white/70">Type:</strong> 
                <span className={`ml-2 px-2 py-0.5 rounded-full text-xs font-medium ${getEventTypeColor(eventData.eventType)}`}>
                    {eventData.eventType}
                </span>
            </p>
            {eventData.notionPageId && (
                 <p className="col-span-2"><strong className="text-soda-white/70">Notion:</strong> 
                    <a href={`https://notion.so/${eventData.notionPageId.replace(/-/g, '')}`} target="_blank" rel="noopener noreferrer" className="ml-1 text-soda-blue hover:text-soda-red">View Page</a>
                </p>
            )}
          </div>
          {eventData.participants && eventData.participants.length > 0 ? (
            <div className="overflow-x-auto">
              <table className="min-w-full table-auto text-sm">
                <thead className="bg-soda-black/30 text-soda-white/70">
                  <tr>
                    <th className="px-3 py-2 text-left">Officer</th>
                    <th className="px-3 py-2 text-left">Role</th>
                    <th className="px-3 py-2 text-left">Points</th>
                    <th className="px-3 py-2 text-left">Department</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-soda-white/10">
                  {eventData.participants.map((p, index) => (
                    <tr key={p.participantId || index} className="hover:bg-soda-black/20">
                      <td className="px-3 py-2 whitespace-nowrap">{p.officerName}</td>
                      <td className="px-3 py-2 whitespace-nowrap">{p.role || 'N/A'}</td>
                      <td className="px-3 py-2 whitespace-nowrap">{p.points}</td>
                      <td className="px-3 py-2 whitespace-nowrap">{p.officerDepartment || 'N/A'}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          ) : (
            <p className="text-soda-white/70 text-center py-4">No participant data for this event.</p>
          )}
        </div>
      </div>
    </div>
  );
};

const OCPDetails = () => {
  useAuthToken();
  const { currentOrg } = useAuth();
  const { 
    goToDashboard,
    goToUsers, 
    goToLeaderboard,
    goToAddPoints,
    goToPanel,
    goToJeopardy 
  } = useOrgNavigation();
  const [expandedOfficer, setExpandedOfficer] = useState(null);
  
  const [leaderboard, setLeaderboard] = useState([]);
  const [leaderboardLoading, setLeaderboardLoading] = useState(true);
  const [leaderboardError, setLeaderboardError] = useState(null); // Specific error for leaderboard

  // State for timeline filters
  const [startDate, setStartDate] = useState(''); // Format YYYY-MM
  const [endDate, setEndDate] = useState('');     // Format YYYY-MM
  
  const [allEvents, setAllEvents] = useState([]);
  const [eventsLoading, setEventsLoading] = useState(true);
  
  const [syncNotification, setSyncNotification] = useState({
    open: false,
    message: '',
    type: 'info' // 'info', 'success', 'warning', 'error'
  });
  const [syncing, setSyncing] = useState(false);
  const [error, setError] = useState(null);
  
  const [diagnosingOfficers, setDiagnosingOfficers] = useState(false);
  const [fixingOfficers, setFixingOfficers] = useState(false);
  const [debugSyncing, setDebugSyncing] = useState(false);
  const [diagnosticResults, setDiagnosticResults] = useState(null);
  const [showAddContributionModal, setShowAddContributionModal] = useState(false);
  const [groupedEvents, setGroupedEvents] = useState([]);
  const [showEventParticipantsModal, setShowEventParticipantsModal] = useState(false);
  const [selectedEventForModal, setSelectedEventForModal] = useState(null);



  const fetchAllEvents = useCallback(async () => {
    setEventsLoading(true);
    setError(null);
    try {
      const response = await apiClient.get('/api/ocp/events');
      const data = response.data;
      if (data.status === 'success' && Array.isArray(data.events)) {
        const processedEvents = data.events.map(event => ({
          ...event,
          officer_name: event.officer?.name || 'Unknown',
          officer_department: event.officer?.department || 'Unknown',
          officer_title: event.officer?.title || 'Unknown'
        }));
        setAllEvents(processedEvents);
      } else {
        setError(`Failed to fetch events: ${data.message || 'Invalid response format'}`);
      }
    } catch (err) {
      setError(`Error fetching events: ${err.message}`);
    } finally {
      setEventsLoading(false);
    }
  }, []);

  const fetchLeaderboard = useCallback(async (sDate, eDate) => {
    setLeaderboardLoading(true);
    setLeaderboardError(null);
    let url = '/api/ocp/officers';
    const params = new URLSearchParams();
    if (sDate) params.append('start_date', sDate);
    if (eDate) params.append('end_date', eDate);
    if (params.toString()) url += `?${params.toString()}`;

    try {
      const response = await apiClient.get(url);
      const data = response.data;
      if (data.status === 'success') {
        setLeaderboard(data.officers || []);
      } else {
        console.error('Error fetching leaderboard:', data.message);
        setLeaderboardError(data.message || 'Failed to fetch leaderboard');
        setLeaderboard([]); // Clear leaderboard on error
      }
    } catch (err) {
      console.error('Error fetching leaderboard:', err);
      setLeaderboardError(`Error fetching leaderboard: ${err.message}`);
      setLeaderboard([]); // Clear leaderboard on error
    } finally {
      setLeaderboardLoading(false);
    }
  }, []);

  const fetchInitialData = useCallback(async () => {
    // Fetch leaderboard with current date filters
    fetchLeaderboard(startDate, endDate);
    // Fetch all events (currently not filtered by date, but could be in future)
    fetchAllEvents();
  }, [fetchAllEvents, fetchLeaderboard, startDate, endDate]);

  useEffect(() => {
    fetchInitialData();
  }, [fetchInitialData]);

  useEffect(() => {
    if (allEvents && allEvents.length > 0) {
      const groups = {};
      allEvents.forEach(event => {
        const eventKey = event.notion_page_id || `${event.event}-${event.timestamp}`;
        if (!groups[eventKey]) {
          groups[eventKey] = {
            key: eventKey,
            eventName: event.event,
            eventType: event.event_type || 'Other',
            eventDate: event.timestamp, 
            notionPageId: event.notion_page_id,
            participants: []
          };
        }
        groups[eventKey].participants.push({
          officerName: event.officer_name,
          officerDepartment: event.officer_department,
          role: event.role,
          points: event.points,
          participantId: event.officer?.uuid || event.officer_name
        });
      });
      setGroupedEvents(Object.values(groups));
    } else {
      setGroupedEvents([]);
    }
  }, [allEvents]);
  
  const triggerSyncAndRefresh = useCallback(async (syncFunction, setLoadingState, successMessagePrefix) => {
    setLoadingState(true);
    setError(null);
    try {
      const response = await syncFunction();
      const data = response.data;
      if (data.status === 'success') {
        setSyncNotification({
          open: true,
          message: `${successMessagePrefix} successful. Added: ${data.added_points_count || 0}, Updated: ${data.updated_points_count || 0}. ${data.message || ''}`.trim(),
          type: 'success'
        });
        fetchInitialData();
      } else if (data.status === 'warning') {
        setSyncNotification({ open: true, message: data.message || `${successMessagePrefix} completed with warnings.`, type: 'warning' });
      } else {
        setSyncNotification({ open: true, message: data.message || `${successMessagePrefix} failed.`, type: 'error' });
      }
      if (data.details) setDiagnosticResults({ title: `${successMessagePrefix} Results`, message: data.message, details: data });
    } catch (err) {
      setSyncNotification({ open: true, message: `Failed to connect to server for ${successMessagePrefix.toLowerCase()}.`, type: 'error' });
    } finally {
      setLoadingState(false);
    }
  }, [fetchInitialData]);

  const syncWithNotion = () => triggerSyncAndRefresh(
    () => apiClient.post('/api/ocp/sync-from-notion'),
    setSyncing,
    "Notion Sync"
  ).then(() => fetchLeaderboard(startDate, endDate)); // Refresh leaderboard after sync

  const debugSyncWithNotion = () => triggerSyncAndRefresh(
    () => apiClient.post('/api/ocp/debug-sync-from-notion'),
    setDebugSyncing,
    "Debug Sync"
  ).then(() => fetchLeaderboard(startDate, endDate)); // Refresh leaderboard after sync
  
  const diagnoseUnknownOfficers = async () => {
    setDiagnosingOfficers(true);
    setDiagnosticResults(null);
    setError(null);
    try {
      let response = await apiClient.get('/api/ocp/diagnose-unknown-officers')
        .catch(err => {
            if (err.response && (err.response.status === 405 || err.response.status === 404)) {
                return apiClient.post('/api/ocp/diagnose-unknown-officers');
            }
            throw err;
        });
      const data = response.data;
      setDiagnosticResults({
        title: 'Officer Diagnosis Results',
        message: `Found ${data.total_issues || 0} issues. Missing UUIDs: ${data.missing_uuid_count || 0}, Unknown Names: ${data.unknown_name_count || 0}. (Department/email issues ignored by this diagnosis).`,
        details: data
      });
      setSyncNotification({ open: true, message: `Officer diagnosis complete. Found ${data.total_issues || 0} issues.`, type: 'info' });
    } catch (err) {
      setSyncNotification({ open: true, message: 'Error diagnosing officers.', type: 'error' });
    } finally {
      setDiagnosingOfficers(false);
    }
  };
  
  const fixUnknownOfficers = () => triggerSyncAndRefresh(
    () => apiClient.post('/api/ocp/repair-officers'),
    setFixingOfficers,
    "Officer Repair"
  ).then(() => fetchLeaderboard(startDate, endDate)); // Refresh leaderboard after repair

  const fetchOfficerContributions = async (officerIdentifier) => {
    if (!officerIdentifier) return;
    let url = `/api/ocp/officer/${officerIdentifier}/contributions`;
    const params = new URLSearchParams();
    // Use the global startDate and endDate for consistency when expanding
    if (startDate) params.append('start_date', startDate);
    if (endDate) params.append('end_date', endDate);
    if (params.toString()) url += `?${params.toString()}`;

    try {
      const response = await apiClient.get(url);
      const data = response.data;
      if (data.status === 'success') {
        setLeaderboard(prevLeaderboard => 
          prevLeaderboard.map(officer => 
            officer.uuid === officerIdentifier || officer.email === officerIdentifier 
            ? { ...officer, contributions: data.contributions }
            : officer
          )
        );
      }
    } catch (err) {
      console.error('Error fetching officer contributions:', err);
      setError('Could not load officer contributions.');
    }
  };

  const handleOfficerClick = (officer) => {
    if (expandedOfficer === officer.uuid) {
      setExpandedOfficer(null);
    } else {
      setExpandedOfficer(officer.uuid);
      // Fetch contributions if not already fetched or if filters might have changed
      // The contributions fetched will now respect the timeline filters
      fetchOfficerContributions(officer.uuid);
    }
  };
  
  const handleCloseNotification = () => setSyncNotification({ ...syncNotification, open: false });

  const handleFilterApply = () => {
    fetchLeaderboard(startDate, endDate);
    // If an officer is expanded, re-fetch their contributions with new dates
    if (expandedOfficer) {
      fetchOfficerContributions(expandedOfficer);
    }
  };

  const handleFilterClear = () => {
    setStartDate('');
    setEndDate('');
    fetchLeaderboard('', ''); // Fetch with no filters
    if (expandedOfficer) {
      fetchOfficerContributions(expandedOfficer); // Re-fetch with no filters
    }
  };

  if (leaderboardLoading && !leaderboard.length) { // Show loading only if leaderboard is empty
    return (
      <OrganizationNavbar>
        <div className="flex items-center justify-center py-12">
          <div className="text-center">
            <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-blue-500 mx-auto mb-4"></div>
            <p className="text-gray-400">Loading OCP System...</p>
          </div>
        </div>
      </OrganizationNavbar>
    );
  }

  return (
    <OrganizationNavbar>
      <div className="max-w-7xl mx-auto">
        <div className="flex flex-col sm:flex-row justify-between items-center mb-6">
          <h1 className="text-3xl sm:text-4xl font-bold text-soda-white tracking-tight mb-4 sm:mb-0">
            OCP System
          </h1>
        </div>

        {/* Consolidated Button Group */}
        <div className="grid grid-cols-1 xs:grid-cols-2 sm:grid-cols-2 md:grid-cols-3 lg:grid-cols-5 gap-3 md:gap-4 mb-8">
            {[ 
              {label: 'Sync Notion', action: syncWithNotion, loading: syncing, Icon: FaSync, color: "#007AFF"},
              {label: 'Log Contribution', action: () => setShowAddContributionModal(true), loading: false, Icon: FaPlusCircle, color: "#007AFF"}
            ].map(btn => (
              <StarBorder 
                key={btn.label} 
                onClick={btn.action} 
                disabled={syncing || debugSyncing || diagnosingOfficers || fixingOfficers || btn.loading} 
                color={btn.color} 
                className="w-full py-2 text-sm"
                as="button"
              >
                <div className="flex items-center justify-center">
                  <btn.Icon className={`h-5 w-5 mr-2 shrink-0 ${btn.loading ? 'animate-spin' : ''}`} />
                  <span className="text-center">{btn.loading ? `${btn.label.split(' ')[0]}ing...` : btn.label}</span>
                </div>
              </StarBorder>
            ))}
        </div>

        {error && (
            <div className="bg-red-800/30 border border-red-700 text-red-300 px-4 py-3 rounded-md relative mb-6" role="alert">
                <strong className="font-bold"><FaExclamationTriangle className="inline mr-2"/>Error: </strong>
                <span className="block sm:inline">{error}</span>
            </div>
        )}

        {diagnosticResults && (
          <div className="bg-soda-gray/70 backdrop-blur-xl p-4 md:p-6 rounded-xl shadow-xl mb-8 border border-soda-white/10">
            <h3 className="text-xl font-semibold text-soda-white mb-2">{diagnosticResults.title}</h3>
            <p className="text-soda-white/80 mb-3">{diagnosticResults.message}</p>
            {diagnosticResults.details && diagnosticResults.details.issues_by_event && (
              <div className="max-h-60 overflow-y-auto text-xs p-2 bg-soda-black/30 rounded-md">
                <pre>{JSON.stringify(diagnosticResults.details.issues_by_event, null, 2)}</pre>
              </div>
            )}
             <p className="text-xs text-soda-white/60 mt-2">Check server logs for full details if applicable.</p>
          </div>
        )}

        {/* Section 1: Officers Leaderboard */}
        <div className="mb-12">
          <h2 className="text-2xl font-semibold text-soda-blue mb-4">Officers Leaderboard</h2>
          
          {/* Timeline Filter UI */} 
          <div className="bg-soda-gray/70 backdrop-blur-md p-6 rounded-xl mb-6 border border-soda-white/10 shadow-lg">
            <h3 className="text-lg font-semibold text-soda-white mb-4 flex items-center">
              <FaSearchDollar className="mr-2 text-soda-blue" />
              Filter by Date Range
            </h3>
            <div className="flex flex-col sm:flex-row gap-4 items-end">
              <div className="flex-1 min-w-[180px]">
                <label htmlFor="start-date" className="block text-sm font-medium text-soda-white/90 mb-2">
                  Start Date (YYYY-MM)
                </label>
                <div className="relative">
                  <input 
                    type="month" 
                    id="start-date" 
                    value={startDate}
                    onChange={(e) => setStartDate(e.target.value)}
                    className="w-full p-3 rounded-lg bg-soda-black/60 border border-soda-white/30 text-soda-white placeholder-soda-white/50 focus:ring-2 focus:ring-soda-blue focus:border-soda-blue transition-all duration-200 [color-scheme:dark]"
                    style={{
                      WebkitAppearance: 'none',
                      MozAppearance: 'none',
                      appearance: 'none'
                    }}
                  />
                </div>
              </div>
              <div className="flex-1 min-w-[180px]">
                <label htmlFor="end-date" className="block text-sm font-medium text-soda-white/90 mb-2">
                  End Date (YYYY-MM)
                </label>
                <div className="relative">
                  <input 
                    type="month" 
                    id="end-date" 
                    value={endDate}
                    onChange={(e) => setEndDate(e.target.value)}
                    className="w-full p-3 rounded-lg bg-soda-black/60 border border-soda-white/30 text-soda-white placeholder-soda-white/50 focus:ring-2 focus:ring-soda-blue focus:border-soda-blue transition-all duration-200 [color-scheme:dark]"
                    style={{
                      WebkitAppearance: 'none',
                      MozAppearance: 'none',
                      appearance: 'none'
                    }}
                  />
                </div>
              </div>
              <div className="flex gap-3 mt-2 sm:mt-0">
                <StarBorder 
                  color="#007AFF" 
                  onClick={handleFilterApply} 
                  className="py-2.5 text-sm font-medium" 
                  as="button"
                >
                  Apply Filters
                </StarBorder>
                <StarBorder 
                  color="#FF3B30" 
                  onClick={handleFilterClear} 
                  className="py-2.5 text-sm font-medium" 
                  as="button"
                >
                  Clear Filters
                </StarBorder>
              </div>
            </div>
          </div>

          {leaderboardLoading && <p className="text-center text-soda-white/70 py-4">Loading leaderboard...</p>}
          {leaderboardError && 
            <div className="bg-red-800/30 border border-red-700 text-red-300 px-4 py-3 rounded-md relative mb-4" role="alert">
                <strong className="font-bold"><FaExclamationTriangle className="inline mr-2"/>Error: </strong>
                <span className="block sm:inline">{leaderboardError}</span>
            </div>
          }

          {!leaderboardLoading && !leaderboardError && leaderboard.length === 0 && (
            <p className="text-center text-soda-white/70 py-8">No officers found for the selected criteria.</p>
          )}

          {!leaderboardError && leaderboard.length > 0 && (
            <div className="bg-soda-gray/70 backdrop-blur-xl shadow-2xl rounded-xl overflow-hidden border border-soda-white/10">
              <div className="overflow-x-auto">
                <table className="min-w-full table-auto text-left text-soda-white/90">
                  <thead className="bg-soda-black/30 text-soda-white/70 uppercase text-xs tracking-wider">
                    <tr>
                      {['Name', 'Email', 'Title', 'Department', 'Total Points', 'Actions'].map(header => (
                        <th key={header} className="px-2 py-2 md:px-4 md:py-3">{header}</th>
                      ))}
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-soda-white/10">
                  {leaderboard.map((officer) => (
                    <React.Fragment key={officer.uuid}>
                        <tr className="hover:bg-soda-black/20 transition-colors">
                          <td className="px-2 py-2 md:px-4 md:py-3 whitespace-nowrap">{officer.name}</td>
                          <td className="px-2 py-2 md:px-4 md:py-3 whitespace-nowrap">{officer.email || 'N/A'}</td>
                          <td className="px-2 py-2 md:px-4 md:py-3 whitespace-nowrap">{officer.title || 'N/A'}</td>
                          <td className="px-2 py-2 md:px-4 md:py-3 whitespace-nowrap">{officer.department || 'N/A'}</td>
                          <td className="px-2 py-2 md:px-4 md:py-3 whitespace-nowrap font-semibold">{officer.total_points}</td>
                          <td className="px-2 py-2 md:px-4 md:py-3 whitespace-nowrap">
                            <button 
                              className="text-soda-blue hover:text-soda-red transition-colors text-sm py-1 px-2 rounded-md border border-soda-blue hover:border-soda-red"
                            onClick={() => handleOfficerClick(officer)}
                          >
                              {expandedOfficer === officer.uuid ? 'Hide' : 'Show'} Events
                            </button>
                          </td>
                        </tr>
                        {expandedOfficer === officer.uuid && (
                          <tr>
                            <td colSpan={6} className="p-0 bg-soda-black/10">
                              <div className="p-2 md:p-4">
                                <h4 className="text-md font-semibold text-soda-white mb-2">Events for {officer.name}</h4>
                                {officer.contributions && officer.contributions.length > 0 ? (
                                  <div className="overflow-x-auto rounded-md border border-soda-white/10">
                                    <table className="min-w-full text-xs">
                                      <thead className="bg-soda-gray/50">
                                        <tr>
                                          {['Event', 'Type', 'Role', 'Points', 'Date'].map(th => 
                                            <th key={th} className="px-2 py-1.5 md:px-3 md:py-2 text-left whitespace-nowrap">{th}</th>) }
                                        </tr>
                                      </thead>
                                      <tbody className="divide-y divide-soda-white/5">
                                    {officer.contributions.map((contribution) => (
                                          <tr key={contribution.id} className="hover:bg-soda-black/30">
                                            <td className="px-2 py-1.5 md:px-3 md:py-2 whitespace-nowrap">{contribution.event}</td>
                                            <td className="px-2 py-1.5 md:px-3 md:py-2 whitespace-nowrap">
                                              <span className={`px-2 py-0.5 rounded-full text-xs font-medium ${getEventTypeColor(contribution.event_type)}`}>
                                                {contribution.event_type || 'Other'}
                                              </span>
                                            </td>
                                            <td className="px-2 py-1.5 md:px-3 md:py-2 whitespace-nowrap">{contribution.role || 'N/A'}</td>
                                            <td className="px-2 py-1.5 md:px-3 md:py-2 whitespace-nowrap">{contribution.points}</td>
                                            <td className="px-2 py-1.5 md:px-3 md:py-2 whitespace-nowrap">{formatDate(contribution.timestamp)}</td>
                                          </tr>
                                        ))}
                                      </tbody>
                                    </table>
                                  </div>
                                ) : (
                                  <p className="text-soda-white/60 text-sm text-center py-4">No contributions found for this officer{startDate || endDate ? ' in the selected date range' : ''} or still loading.</p>
                                )}
                              </div>
                            </td>
                          </tr>
                      )}
                    </React.Fragment>
                  ))}
                    {leaderboard.length === 0 && (
                       <tr><td colSpan={6} className="text-center py-8 text-soda-white/70">No officers found in the leaderboard.</td></tr>
                    )}
                  </tbody>
                </table>
              </div>
            </div>
          )}
        </div>

        {/* Section 2: All Events */}
        <div>
          <div className="flex flex-col sm:flex-row justify-between items-center mb-4">
            <h2 className="text-2xl font-semibold text-soda-blue mb-2 sm:mb-0">All Contribution Events</h2>
            <button 
                className="flex items-center bg-soda-blue hover:bg-soda-red text-soda-white font-semibold py-2 px-4 rounded-lg shadow-md transition-colors duration-150 disabled:opacity-50"
            onClick={fetchAllEvents}
            disabled={eventsLoading}
            >
              <FaRedo className={`mr-2 ${eventsLoading ? 'animate-spin' : ''}`} />
              {eventsLoading ? 'Refreshing...' : 'Refresh All Events'}
            </button>
          </div>

          {eventsLoading && !groupedEvents.length ? (
            <p className="text-center text-soda-white/70 py-8">Loading all events...</p>
          ) : !eventsLoading && groupedEvents.length === 0 && !error ? (
            <p className="text-center text-soda-white/70 py-8">No events found.</p>
          ) : groupedEvents.length > 0 && (
            <>
            {/* Summary Cards */}
            <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4 mb-8">
              {[ 
                {title: 'Total Unique Event Instances', value: groupedEvents.length},
                {title: 'Total Points Logged (All Events)', value: allEvents.reduce((sum, event) => sum + event.points, 0)},
                {title: 'Unique Event Types (Across all groups)', value: new Set(groupedEvents.map(gEvent => gEvent.eventType)).size},
                {title: 'Total Participations Logged', value: allEvents.length}
              ].map(card => (
                <div key={card.title} className="bg-soda-gray/70 backdrop-blur-xl p-4 rounded-xl shadow-lg border border-soda-white/10">
                  <h3 className="text-soda-white/70 text-sm font-medium mb-1 truncate">{card.title}</h3>
                  <p className="text-soda-white text-2xl font-bold">{card.value}</p>
                </div>
              ))}
            </div>

            {/* Events Table - now iterates over groupedEvents */}
            <div className="bg-soda-gray/70 backdrop-blur-xl shadow-2xl rounded-xl overflow-hidden border border-soda-white/10">
              <div className="overflow-x-auto">
                <table className="min-w-full table-auto text-left text-soda-white/90">
                  <thead className="bg-soda-black/30 text-soda-white/70 uppercase text-xs tracking-wider">
                    <tr>
                      <th className="px-2 py-2 md:px-4 md:py-3 whitespace-nowrap">Event Name</th>
                      <th className="px-2 py-2 md:px-4 md:py-3 whitespace-nowrap">Type</th>
                      <th className="px-2 py-2 md:px-4 md:py-3 whitespace-nowrap">Date</th>
                      <th className="px-2 py-2 md:px-4 md:py-3 whitespace-nowrap">Participants</th>
                      <th className="px-2 py-2 md:px-4 md:py-3 whitespace-nowrap">Actions</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-soda-white/10">
                    {groupedEvents.map((gEvent) => (
                        <tr key={gEvent.key} className="hover:bg-soda-black/20 transition-colors">
                          <td className="px-2 py-2 md:px-4 md:py-3 whitespace-nowrap">{gEvent.eventName}</td>
                          <td className="px-2 py-2 md:px-4 md:py-3 whitespace-nowrap">
                            <span className={`px-2 py-0.5 rounded-full text-xs font-medium ${getEventTypeColor(gEvent.eventType)}`}>
                                {gEvent.eventType}
                            </span>
                          </td>
                          <td className="px-2 py-2 md:px-4 md:py-3 whitespace-nowrap">{formatDate(gEvent.eventDate)}</td>
                          <td className="px-2 py-2 md:px-4 md:py-3 whitespace-nowrap text-center">{gEvent.participants.length}</td>
                          <td className="px-2 py-2 md:px-4 md:py-3 whitespace-nowrap">
                            <button 
                                onClick={() => { setSelectedEventForModal(gEvent); setShowEventParticipantsModal(true); }}
                                className="text-soda-blue hover:text-soda-red transition-colors text-sm py-1 px-2 rounded-md border border-soda-blue hover:border-soda-red"
                            >
                                View Participants
                            </button>
                          </td>
                        </tr>
                      ))}
                  </tbody>
                </table>
              </div>
            </div>
          </>
        )}
        </div>

        {/* Notification Area */}
        {syncNotification.open && (
            <div className={`fixed bottom-5 right-5 p-4 rounded-lg shadow-xl text-soda-white max-w-sm z-50 
            ${syncNotification.type === 'success' ? 'bg-green-600/90 border border-green-500' : 
              syncNotification.type === 'warning' ? 'bg-yellow-600/90 border border-yellow-500' : 
              syncNotification.type === 'error' ? 'bg-red-700/90 border border-red-600' : 
              'bg-soda-gray/90 border border-soda-white/20'}
            backdrop-blur-md`}
          >
            <div className="flex justify-between items-center">
                <p>{syncNotification.message}</p>
                <button onClick={handleCloseNotification} className="ml-4 text-xl font-bold hover:opacity-75">&times;</button>
            </div>
          </div>
        )}
      </div>
      
      <AddContributionModal 
        isOpen={showAddContributionModal} 
        onClose={() => {
          setShowAddContributionModal(false);
        }}
        onAdd={async (contributionData) => {
          try {
            const response = await apiClient.post('/api/ocp/add-contribution', contributionData);
            const result = response.data;
            if (response.status >= 200 && response.status < 300 && result.status !== 'error') {
                setSyncNotification({ 
                  open: true, 
                  message: result.message || 'Contribution(s) added successfully!', 
                  type: 'success'
                });
                setShowAddContributionModal(false);
                fetchInitialData();
                return true; // Indicate success to modal
            } else {
                setSyncNotification({ 
                  open: true, 
                  message: result.message || 'Failed to add contribution.', 
                  type: 'error'
                });
                return false;
            }
          } catch (err) {
            setSyncNotification({ 
              open: true, 
              message: err.response?.data?.message || err.message || 'An error occurred.', 
              type: 'error'
            });
            return false;
          }
        }}
      />

      <EventParticipantsModal 
        isOpen={showEventParticipantsModal} 
        onClose={() => setShowEventParticipantsModal(false)} 
        eventData={selectedEventForModal} 
      />
    </OrganizationNavbar>
  );
};

export default OCPDetails; 