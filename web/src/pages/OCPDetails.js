import React, { useState, useEffect, useCallback, useRef, useReducer } from 'react';
import apiClient from '../components/utils/axios';
import useAuthToken from '../hooks/userAuth';
import { useAuth } from '../components/auth/AuthContext';
import { FaUsers, FaSignOutAlt, FaTachometerAlt, FaClipboardList, FaCogs, FaRedo, FaSearchDollar, FaWrench, FaExclamationTriangle, FaSync, FaFlask, FaPlusCircle, FaTimes } from 'react-icons/fa';

import OrganizationNavbar from '../components/shared/OrganizationNavbar';
import StarBorder from '../components/ui/StarBorder';

// --- Helper Functions ---

/**
 * Formats a date string into a more readable format (e.g., "Aug 7, 2025").
 * @param {string} dateString - The ISO date string to format.
 * @returns {string} The formatted date or 'N/A'.
 */
const formatDate = (dateString) => {
  if (!dateString) return 'N/A';
  try {
    return new Date(dateString).toLocaleDateString('en-US', { year: 'numeric', month: 'short', day: 'numeric' });
  } catch (e) {
    console.error("Date formatting error:", e);
    return dateString;
  }
};

/**
 * Returns a Tailwind CSS class string for styling based on event type.
 * @param {string} eventType - The type of the event.
 * @returns {string} Tailwind CSS classes for color and background.
 */
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

// --- Child Components ---

/**
 * A modal for logging new contributions.
 * It handles its own internal state for form inputs and fetches available officers.
 */
const AddContributionModal = ({ isOpen, onClose, onAdd }) => {
  // State for the form fields
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

  const modalRef = useRef(null);
  
  // Resets the form to its initial state
  const resetForm = useCallback(() => {
    setSelectedOfficers([]);
    setCustomOfficerName('');
    setEventDescription('');
    setPoints(1);
    setRole('');
    setEventType('Other');
    setEventDate(new Date().toISOString().split('T')[0]);
    setFormError('');
  }, []);

  // Fetch available officers when the modal is opened
  useEffect(() => {
    const fetchAvailableOfficers = async () => {
      setLoadingOfficers(true);
      try {
        const response = await apiClient.get('/api/ocp/officer-names');
        if (response.data.status === 'success') {
          setAvailableOfficers(response.data.officers);
        }
      } catch (error) {
        console.error('Error fetching officer names:', error);
        setFormError('Could not load officer list.');
      } finally {
        setLoadingOfficers(false);
      }
    };
    if (isOpen) {
      fetchAvailableOfficers();
    }
  }, [isOpen]);

  // Handle clicks outside the modal to close it
  useEffect(() => {
    if (!isOpen) return;
    const handleClickOutside = (event) => {
      if (modalRef.current && !modalRef.current.contains(event.target)) {
        onClose();
      }
    };
    document.addEventListener('mousedown', handleClickOutside);
    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, [isOpen, onClose]);

  if (!isOpen) return null;

  const handleOfficerSelect = (officer) => {
    if (!selectedOfficers.find(o => o.uuid === officer.uuid)) {
      setSelectedOfficers(prev => [...prev, officer]);
    }
  };

  const handleRemoveOfficer = (officerToRemove) => {
    setSelectedOfficers(prev => prev.filter(o => o.uuid !== officerToRemove.uuid));
  };

  const handleAddCustomOfficer = () => {
    const trimmedName = customOfficerName.trim();
    if (trimmedName && !selectedOfficers.find(o => o.name === trimmedName)) {
      setSelectedOfficers(prev => [...prev, { name: trimmedName, uuid: `custom_${Date.now()}` }]);
      setCustomOfficerName('');
    }
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    if (selectedOfficers.length === 0 || !eventDescription) {
      setFormError('At least one officer and an event description are required.');
      return;
    }
    setIsSubmitting(true);
    setFormError('');

    const contributionData = {
      names: selectedOfficers.map(officer => officer.name),
      event: eventDescription,
      points: parseInt(points, 10) || 1,
      role: role || undefined,
      event_type: eventType || undefined,
      timestamp: eventDate ? new Date(eventDate).toISOString() : undefined,
    };
    
    const success = await onAdd(contributionData);
    setIsSubmitting(false);

    if (success) {
      resetForm();
      onClose();
    }
  };

  return (
    <div className="fixed inset-0 bg-soda-black/80 backdrop-blur-md flex items-center justify-center z-50 p-4">
      <div ref={modalRef} className="bg-soda-gray/90 backdrop-blur-xl rounded-xl shadow-2xl w-full max-w-lg mx-auto max-h-[90vh] flex flex-col overflow-hidden border border-soda-white/10">
        <div className="p-5 border-b border-soda-white/10 flex justify-between items-center">
          <h2 className="text-xl font-semibold text-soda-white">Log New Contribution</h2>
          <button onClick={onClose} className="text-soda-white/70 hover:text-soda-white transition-colors">
            <FaTimes className="h-6 w-6" />
          </button>
        </div>
        <form onSubmit={handleSubmit} className="p-6 space-y-4 overflow-y-auto">
          {formError && <p className="text-red-400 text-sm">{formError}</p>}
          
          {/* Officer Selection */}
          <div>
            <label className="block text-sm font-medium text-soda-white/90 mb-2">Select Officers <span className="text-soda-red">*</span></label>
            <div className="mb-3">
              {loadingOfficers ? <p className="text-soda-white/60">Loading...</p> : (
                <select 
                  id="existingOfficers" 
                  onChange={(e) => {
                    const selectedUuid = e.target.value;
                    if (selectedUuid) {
                      const officer = availableOfficers.find(o => o.uuid === selectedUuid);
                      if (officer) handleOfficerSelect(officer);
                      e.target.value = ''; // Reset dropdown
                    }
                  }}
                  className="w-full p-2.5 rounded-md bg-soda-black/50 border border-soda-white/20 text-soda-white focus:ring-soda-blue focus:border-soda-blue"
                >
                  <option value="">-- Select an existing officer --</option>
                  {availableOfficers.map((officer) => (
                    <option key={officer.uuid} value={officer.uuid}>{officer.name}</option>
                  ))}
                </select>
              )}
            </div>
            <div className="flex gap-2 mb-3">
              <input 
                type="text" 
                id="customOfficer" 
                value={customOfficerName} 
                onChange={(e) => setCustomOfficerName(e.target.value)}
                onKeyPress={(e) => { if (e.key === 'Enter') { e.preventDefault(); handleAddCustomOfficer(); } }}
                placeholder="Or add a new officer name"
                className="flex-1 p-2.5 rounded-md bg-soda-black/50 border border-soda-white/20"
              />
              <button type="button" onClick={handleAddCustomOfficer} disabled={!customOfficerName.trim()} className="px-4 py-2.5 bg-soda-blue hover:bg-soda-blue/80 disabled:bg-soda-gray/50 text-white rounded-md">
                Add
              </button>
            </div>
            {selectedOfficers.length > 0 && (
              <div className="flex flex-wrap gap-2">
                {selectedOfficers.map(officer => (
                  <div key={officer.uuid} className="flex items-center bg-soda-blue/20 text-soda-blue rounded-md px-3 py-1 text-sm">
                    <span>{officer.name}</span>
                    <button type="button" onClick={() => handleRemoveOfficer(officer)} className="ml-2 hover:text-soda-red">
                      <FaTimes className="h-3 w-3" />
                    </button>
                  </div>
                ))}
              </div>
            )}
          </div>

          {/* Other Form Fields */}
          <div>
            <label htmlFor="eventDescription" className="block text-sm font-medium text-soda-white/90 mb-1">Event Description <span className="text-soda-red">*</span></label>
            <input type="text" id="eventDescription" value={eventDescription} onChange={e => setEventDescription(e.target.value)} required className="w-full p-2.5 rounded-md bg-soda-black/50 border border-soda-white/20" />
          </div>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div>
              <label htmlFor="points" className="block text-sm font-medium text-soda-white/90 mb-1">Points</label>
              <input type="number" id="points" value={points} onChange={e => setPoints(Math.max(0, parseInt(e.target.value, 10) || 0))} className="w-full p-2.5 rounded-md bg-soda-black/50 border border-soda-white/20" />
            </div>
            <div>
              <label htmlFor="eventType" className="block text-sm font-medium text-soda-white/90 mb-1">Event Type</label>
              <select id="eventType" value={eventType} onChange={e => setEventType(e.target.value)} className="w-full p-2.5 rounded-md bg-soda-black/50 border border-soda-white/20 h-[46px]">
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
            <input type="text" id="role" value={role} onChange={e => setRole(e.target.value)} className="w-full p-2.5 rounded-md bg-soda-black/50 border border-soda-white/20" />
          </div>
          <div>
            <label htmlFor="eventDate" className="block text-sm font-medium text-soda-white/90 mb-1">Event Date</label>
            <input type="date" id="eventDate" value={eventDate} onChange={e => setEventDate(e.target.value)} className="w-full p-2.5 rounded-md bg-soda-black/50 border border-soda-white/20 [color-scheme:dark]" />
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


/**
 * A modal for displaying the participants of a specific event.
 */
const EventParticipantsModal = ({ isOpen, onClose, eventData }) => {
  if (!isOpen || !eventData) return null;

  return (
    <div className="fixed inset-0 bg-soda-black/80 backdrop-blur-md flex items-center justify-center z-50 p-4">
      <div className="bg-soda-gray/90 backdrop-blur-xl rounded-xl shadow-2xl w-full max-w-2xl mx-auto max-h-[90vh] flex flex-col overflow-hidden border border-soda-white/10">
        <div className="p-5 border-b border-soda-white/10 flex justify-between items-center">
          <h2 className="text-xl font-semibold text-soda-white truncate pr-4">Participants: {eventData.eventName}</h2>
          <button onClick={onClose} className="text-soda-white/70 hover:text-soda-white transition-colors">
            <FaTimes className="h-6 w-6" />
          </button>
        </div>
        <div className="p-6 space-y-4 overflow-y-auto">
          {eventData.participants?.length > 0 ? (
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

// --- Main Page Component ---

const OCPDetails = () => {
  useAuthToken(); // Auth token hook

  // --- State Management ---
  const [leaderboard, setLeaderboard] = useState([]);
  const [leaderboardLoading, setLeaderboardLoading] = useState(true);
  const [leaderboardError, setLeaderboardError] = useState(null);

  const [allEvents, setAllEvents] = useState([]);
  const [eventsLoading, setEventsLoading] = useState(true);
  const [eventsError, setEventsError] = useState(null);

  const [groupedEvents, setGroupedEvents] = useState([]);
  const [expandedOfficer, setExpandedOfficer] = useState(null);

  // Filters and Modals
  const [startDate, setStartDate] = useState('');
  const [endDate, setEndDate] = useState('');
  const [showAddContributionModal, setShowAddContributionModal] = useState(false);
  const [showEventParticipantsModal, setShowEventParticipantsModal] = useState(false);
  const [selectedEventForModal, setSelectedEventForModal] = useState(null);

  // Syncing and Notifications
  const [isSyncing, setIsSyncing] = useState(false);
  const [syncNotification, setSyncNotification] = useState({ open: false, message: '', type: 'info' });

  // --- Data Fetching ---

  const fetchLeaderboard = useCallback(async (sDate, eDate) => {
    setLeaderboardLoading(true);
    setLeaderboardError(null);
    const params = new URLSearchParams();
    if (sDate) params.append('start_date', sDate);
    if (eDate) params.append('end_date', eDate);
    
    try {
      const response = await apiClient.get(`/api/ocp/officers?${params.toString()}`);
      if (response.data.status === 'success') {
        setLeaderboard(response.data.officers || []);
      } else {
        setLeaderboardError(response.data.message || 'Failed to fetch leaderboard data.');
        setLeaderboard([]);
      }
    } catch (err) {
      setLeaderboardError(`Network Error: ${err.message}`);
      setLeaderboard([]);
    } finally {
      setLeaderboardLoading(false);
    }
  }, []);

  const fetchAllEvents = useCallback(async () => {
    setEventsLoading(true);
    setEventsError(null);
    try {
      const response = await apiClient.get('/api/ocp/events');
      if (response.data.status === 'success' && Array.isArray(response.data.events)) {
        setAllEvents(response.data.events);
      } else {
        setEventsError(response.data.message || 'Invalid response format for events.');
      }
    } catch (err) {
      setEventsError(`Network Error: ${err.message}`);
    } finally {
      setEventsLoading(false);
    }
  }, []);

  const fetchInitialData = useCallback(() => {
    fetchLeaderboard(startDate, endDate);
    fetchAllEvents();
  }, [fetchLeaderboard, fetchAllEvents, startDate, endDate]);

  useEffect(() => {
    fetchInitialData();
  }, [fetchInitialData]);

  // Group events by notion_page_id or a composite key when allEvents data changes
  useEffect(() => {
    if (!allEvents || allEvents.length === 0) {
      setGroupedEvents([]);
      return;
    }
    const groups = allEvents.reduce((acc, event) => {
      const eventKey = event.notion_page_id || `${event.event}-${event.timestamp}`;
      if (!acc[eventKey]) {
        acc[eventKey] = {
          key: eventKey,
          eventName: event.event,
          eventType: event.event_type || 'Other',
          eventDate: event.timestamp,
          notionPageId: event.notion_page_id,
          participants: [],
        };
      }
      acc[eventKey].participants.push({
        officerName: event.officer?.name || 'Unknown',
        officerDepartment: event.officer?.department || 'Unknown',
        role: event.role,
        points: event.points,
        participantId: event.officer?.uuid || event.officer_name,
      });
      return acc;
    }, {});
    setGroupedEvents(Object.values(groups).sort((a, b) => new Date(b.eventDate) - new Date(a.eventDate)));
  }, [allEvents]);

  const fetchOfficerContributions = useCallback(async (officerUuid) => {
    const params = new URLSearchParams();
    if (startDate) params.append('start_date', startDate);
    if (endDate) params.append('end_date', endDate);

    try {
      const url = `/api/ocp/officer/${officerUuid}/contributions?${params.toString()}`;
      const response = await apiClient.get(url);
      if (response.data.status === 'success') {
        setLeaderboard(prev =>
          prev.map(officer =>
            officer.uuid === officerUuid
              ? { ...officer, contributions: response.data.contributions }
              : officer
          )
        );
      } else {
         throw new Error(response.data.message || 'Failed to fetch contributions.');
      }
    } catch (err) {
      console.error('Error fetching contributions:', err);
      setSyncNotification({ open: true, message: `Could not load contributions for officer. ${err.message}`, type: 'error' });
    }
  }, [startDate, endDate]);


  // --- Event Handlers ---

  const handleOfficerClick = useCallback((officer) => {
    const newExpandedOfficer = expandedOfficer === officer.uuid ? null : officer.uuid;
    setExpandedOfficer(newExpandedOfficer);
    // Fetch contributions if expanding and they aren't loaded yet
    if (newExpandedOfficer && !officer.contributions) {
      fetchOfficerContributions(officer.uuid);
    }
  }, [expandedOfficer, fetchOfficerContributions]);

  const handleFilterApply = useCallback(() => {
    fetchLeaderboard(startDate, endDate);
    // If an officer is expanded, their contributions need to be refetched with the new date range
    if (expandedOfficer) {
      fetchOfficerContributions(expandedOfficer);
    }
  }, [startDate, endDate, expandedOfficer, fetchLeaderboard, fetchOfficerContributions]);
  
  const handleFilterClear = useCallback(() => {
    setStartDate('');
    setEndDate('');
    fetchLeaderboard('', ''); // Fetch with cleared filters
    if (expandedOfficer) {
      fetchOfficerContributions(expandedOfficer);
    }
  }, [expandedOfficer, fetchLeaderboard, fetchOfficerContributions]);
  
  const { currentOrg } = useAuth(); // Add this at the top level of the component

  const handleAddContribution = useCallback(async (contributionData) => {
    if (!currentOrg?.prefix) {
      setSyncNotification({
        open: true,
        message: 'No organization selected.',
        type: 'error',
      });
      return false;
    }

    try {
      const response = await apiClient.post(`/api/ocp/${currentOrg.prefix}/add-contribution`, contributionData);
      const result = response.data;

      if (response.status >= 200 && response.status < 300 && result.status !== 'error') {
        setSyncNotification({
          open: true,
          message: result.message || 'Contribution added successfully!',
          type: 'success',
        });
        fetchInitialData(); // Refresh all data
        return true; // Signal success to modal
      } else {
        throw new Error(result.message || 'Failed to add contribution.');
      }
    } catch (err) {
      setSyncNotification({
        open: true,
        message: err.response?.data?.message || err.message,
        type: 'error',
      });
      return false; // Signal failure to modal
    }
  }, [fetchInitialData, currentOrg?.prefix]);

  const handleSyncWithNotion = useCallback(async () => {
    if (!currentOrg?.prefix) {
      setSyncNotification({
        open: true,
        message: 'No organization selected.',
        type: 'error',
      });
      return;
    }

    setIsSyncing(true);
    try {
        const response = await apiClient.post(`/api/ocp/${currentOrg.prefix}/sync-from-notion`);
        const data = response.data;
        if (data.status === 'success') {
            setSyncNotification({
                open: true,
                message: `Notion Sync successful. Added: ${data.added_points_count || 0}, Updated: ${data.updated_points_count || 0}.`,
                type: 'success'
            });
            fetchInitialData(); // Refresh data after a successful sync
        } else {
            throw new Error(data.message || 'Notion sync failed with an unknown error.');
        }
    } catch (err) {
        setSyncNotification({ open: true, message: err.message, type: 'error' });
    } finally {
        setIsSyncing(false);
    }
  }, [fetchInitialData, currentOrg?.prefix]);


  // --- Render Logic ---

  if (leaderboardLoading && leaderboard.length === 0) {
    return (
      <OrganizationNavbar>
        <div className="flex items-center justify-center py-20">
          <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-soda-blue"></div>
        </div>
      </OrganizationNavbar>
    );
  }

  return (
    <OrganizationNavbar>
      <div className="max-w-7xl mx-auto p-4 md:p-6">
        <h1 className="text-3xl sm:text-4xl font-bold text-soda-white tracking-tight mb-8">
          OCP System
        </h1>

        {/* --- Action Buttons --- */}
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4 mb-8">
            <StarBorder as="button" color="#007AFF" onClick={handleSyncWithNotion} disabled={isSyncing} className="py-2 text-sm">
                <div className="flex items-center justify-center">
                    <FaSync className={`h-5 w-5 mr-2 ${isSyncing ? 'animate-spin' : ''}`} />
                    <span>{isSyncing ? 'Syncing...' : 'Sync Notion'}</span>
                </div>
            </StarBorder>
            <StarBorder as="button" color="#34C759" onClick={() => setShowAddContributionModal(true)} disabled={isSyncing} className="py-2 text-sm">
                <div className="flex items-center justify-center">
                    <FaPlusCircle className="h-5 w-5 mr-2" />
                    <span>Log Contribution</span>
                </div>
            </StarBorder>
        </div>

        {/* --- Officers Leaderboard Section --- */}
        <div className="mb-12">
          <h2 className="text-2xl font-semibold text-soda-blue mb-4">Officers Leaderboard</h2>
          
          {/* Date Filter */}
          <div className="bg-soda-gray/70 backdrop-blur-md p-4 md:p-6 rounded-xl mb-6 border border-soda-white/10">
            <div className="flex flex-col sm:flex-row gap-4 items-end">
                <div className="flex-1 min-w-[180px]">
                    <label htmlFor="start-date" className="block text-sm font-medium text-soda-white/90 mb-2">Start Date</label>
                    <input type="month" id="start-date" value={startDate} onChange={(e) => setStartDate(e.target.value)} className="w-full p-3 rounded-lg bg-soda-black/60 border border-soda-white/30 [color-scheme:dark]" />
                </div>
                <div className="flex-1 min-w-[180px]">
                    <label htmlFor="end-date" className="block text-sm font-medium text-soda-white/90 mb-2">End Date</label>
                    <input type="month" id="end-date" value={endDate} onChange={(e) => setEndDate(e.target.value)} className="w-full p-3 rounded-lg bg-soda-black/60 border border-soda-white/30 [color-scheme:dark]" />
                </div>
                <div className="flex gap-3 w-full sm:w-auto">
                    <StarBorder as="button" color="#007AFF" onClick={handleFilterApply} className="py-2.5 text-sm flex-1">Apply</StarBorder>
                    <StarBorder as="button" color="#FF3B30" onClick={handleFilterClear} className="py-2.5 text-sm flex-1">Clear</StarBorder>
                </div>
            </div>
          </div>

          {/* Leaderboard Table */}
          {leaderboardLoading && <p className="text-center text-soda-white/70 py-4">Refreshing leaderboard...</p>}
          {leaderboardError && <p className="text-center text-red-400 py-4">{leaderboardError}</p>}
          {!leaderboardLoading && !leaderboardError && leaderboard.length === 0 && (
            <p className="text-center text-soda-white/70 py-8">No officers found for the selected criteria.</p>
          )}

          {leaderboard.length > 0 && (
            <div className="bg-soda-gray/70 backdrop-blur-xl rounded-xl overflow-hidden border border-soda-white/10">
              <div className="overflow-x-auto">
                <table className="min-w-full table-auto text-left text-soda-white/90">
                  <thead className="bg-soda-black/30 text-soda-white/70 uppercase text-xs">
                    <tr>
                      {['Name', 'Title', 'Department', 'Total Points', 'Actions'].map(header => (
                        <th key={header} className="px-4 py-3">{header}</th>
                      ))}
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-soda-white/10">
                    {leaderboard.map((officer) => (
                      <React.Fragment key={officer.uuid}>
                        <tr className="hover:bg-soda-black/20">
                          <td className="px-4 py-3 whitespace-nowrap">{officer.name}</td>
                          <td className="px-4 py-3 whitespace-nowrap">{officer.title || 'N/A'}</td>
                          <td className="px-4 py-3 whitespace-nowrap">{officer.department || 'N/A'}</td>
                          <td className="px-4 py-3 whitespace-nowrap font-semibold">{officer.total_points}</td>
                          <td className="px-4 py-3 whitespace-nowrap">
                            <button onClick={() => handleOfficerClick(officer)} className="text-soda-blue hover:text-soda-red transition-colors text-sm py-1 px-2 rounded-md border border-soda-blue hover:border-soda-red">
                              {expandedOfficer === officer.uuid ? 'Hide' : 'Show'} Events
                            </button>
                          </td>
                        </tr>
                        {expandedOfficer === officer.uuid && (
                          <tr>
                            <td colSpan={5} className="p-0 bg-soda-black/10">
                              <div className="p-4">
                                {officer.contributions ? (
                                  officer.contributions.length > 0 ? (
                                    <table className="min-w-full text-xs">
                                      <thead className="bg-soda-gray/50">
                                        <tr>
                                          {['Event', 'Type', 'Role', 'Points', 'Date'].map(th => <th key={th} className="px-3 py-2 text-left">{th}</th>)}
                                        </tr>
                                      </thead>
                                      <tbody className="divide-y divide-soda-white/5">
                                        {officer.contributions.map(c => (
                                          <tr key={c.id}>
                                            <td className="px-3 py-2">{c.event}</td>
                                            <td className="px-3 py-2"><span className={`px-2 py-0.5 rounded-full ${getEventTypeColor(c.event_type)}`}>{c.event_type || 'Other'}</span></td>
                                            <td className="px-3 py-2">{c.role || 'N/A'}</td>
                                            <td className="px-3 py-2">{c.points}</td>
                                            <td className="px-3 py-2">{formatDate(c.timestamp)}</td>
                                          </tr>
                                        ))}
                                      </tbody>
                                    </table>
                                  ) : (<p className="text-soda-white/60 text-center py-3">No contributions found in this period.</p>)
                                ) : (<p className="text-soda-white/60 text-center py-3">Loading contributions...</p>)}
                              </div>
                            </td>
                          </tr>
                        )}
                      </React.Fragment>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          )}
        </div>

        {/* --- All Events Section --- */}
        <div>
          <h2 className="text-2xl font-semibold text-soda-blue mb-4">All Contribution Events</h2>
          {eventsLoading && !groupedEvents.length ? (<p>Loading events...</p>) : eventsError ? (<p>{eventsError}</p>) : groupedEvents.length > 0 ? (
            <div className="bg-soda-gray/70 backdrop-blur-xl rounded-xl overflow-hidden border border-soda-white/10">
              <div className="overflow-x-auto">
                <table className="min-w-full table-auto text-left text-soda-white/90">
                  <thead className="bg-soda-black/30 text-soda-white/70 uppercase text-xs">
                    <tr>
                      {['Event Name', 'Type', 'Date', 'Participants', 'Actions'].map(h => <th key={h} className="px-4 py-3">{h}</th>)}
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-soda-white/10">
                    {groupedEvents.map((gEvent) => (
                      <tr key={gEvent.key} className="hover:bg-soda-black/20">
                        <td className="px-4 py-3">{gEvent.eventName}</td>
                        <td className="px-4 py-3"><span className={`px-2 py-0.5 rounded-full text-xs ${getEventTypeColor(gEvent.eventType)}`}>{gEvent.eventType}</span></td>
                        <td className="px-4 py-3">{formatDate(gEvent.eventDate)}</td>
                        <td className="px-4 py-3 text-center">{gEvent.participants.length}</td>
                        <td className="px-4 py-3">
                          <button onClick={() => { setSelectedEventForModal(gEvent); setShowEventParticipantsModal(true); }} className="text-soda-blue hover:text-soda-red text-sm py-1 px-2 rounded-md border border-soda-blue hover:border-soda-red">
                            View Participants
                          </button>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          ) : (<p>No events found.</p>)}
        </div>
      </div>

      {/* --- Modals & Notifications --- */}
      <AddContributionModal
        isOpen={showAddContributionModal}
        onClose={() => setShowAddContributionModal(false)}
        onAdd={handleAddContribution}
      />
      <EventParticipantsModal
        isOpen={showEventParticipantsModal}
        onClose={() => setShowEventParticipantsModal(false)}
        eventData={selectedEventForModal}
      />
      {syncNotification.open && (
        <div className={`fixed bottom-5 right-5 p-4 rounded-lg shadow-xl text-soda-white max-w-sm z-50 backdrop-blur-md
          ${syncNotification.type === 'success' ? 'bg-green-600/90' : syncNotification.type === 'error' ? 'bg-red-700/90' : 'bg-soda-gray/90'}`}>
          <div className="flex justify-between items-center">
            <p>{syncNotification.message}</p>
            <button onClick={() => setSyncNotification({ ...syncNotification, open: false })} className="ml-4 text-xl">&times;</button>
          </div>
        </div>
      )}
    </OrganizationNavbar>
  );
};

export default OCPDetails;