import React, { useState, useEffect } from 'react';
import { useAuth } from '../components/auth/AuthContext';
import OrganizationNavbar from '../components/shared/OrganizationNavbar';
import ThemedLoading from '../components/ui/ThemedLoading';
import { toast } from 'react-toastify';
import { FaCalendarAlt, FaSync, FaCog, FaExternalLinkAlt } from 'react-icons/fa';
import apiClient from '../components/utils/axios';

const Calendar = () => {
  const { currentOrg, getApiClient } = useAuth();
  const [events, setEvents] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [currentDate, setCurrentDate] = useState(new Date());
  const [viewMode, setViewMode] = useState('month'); // 'month', 'week', 'list'

  useEffect(() => {
    if (currentOrg) {
      fetchEvents();
    }
  }, [currentOrg]);

  const fetchEvents = async () => {
    try {
      setLoading(true);
      setError(null);
      
      console.log(`Fetching events for organization: ${currentOrg?.prefix}`);
      
      const response = await apiClient.get(`/api/calendar/${currentOrg.prefix}/events`);
      
      if (response.data.status === 'success') {
        setEvents(response.data.events || []);
        console.log(`Successfully loaded ${response.data.events?.length || 0} events`);
      } else {
        const errorMessage = response.data.message || 'Failed to fetch events';
        setError(errorMessage);
        toast.error(errorMessage);
      }
    } catch (error) {
      console.error('Error fetching events:', error);
      let errorMessage = 'Failed to load events';
      
      if (error.response) {
        // The request was made and the server responded with a status code
        // that falls out of the range of 2xx
        if (error.response.data && error.response.data.message) {
          errorMessage = error.response.data.message;
        } else {
          errorMessage = `HTTP ${error.response.status}: ${error.response.statusText}`;
        }
        console.error('Response error:', error.response.data);
      } else if (error.request) {
        // The request was made but no response was received
        errorMessage = 'No response from server';
        console.error('Request error:', error.request);
      } else {
        // Something happened in setting up the request that triggered an Error
        errorMessage = error.message || 'Network error';
        console.error('Error setting up request:', error.message);
      }
      
      setError(errorMessage);
      toast.error(errorMessage);
    } finally {
      setLoading(false);
    }
  };

  const formatDate = (dateString) => {
    const date = new Date(dateString);
    return date.toLocaleDateString('en-US', {
      weekday: 'short',
      year: 'numeric',
      month: 'short',
      day: 'numeric',
      hour: '2-digit',
      minute: '2-digit'
    });
  };

  const getDaysInMonth = (date) => {
    const year = date.getFullYear();
    const month = date.getMonth();
    const firstDay = new Date(year, month, 1);
    const lastDay = new Date(year, month + 1, 0);
    const daysInMonth = lastDay.getDate();
    const startingDay = firstDay.getDay();
    
    return { daysInMonth, startingDay, year, month };
  };

  const getEventsForDate = (date) => {
    return events.filter(event => {
      const eventDate = new Date(event.start);
      return eventDate.toDateString() === date.toDateString();
    });
  };

  const renderMonthView = () => {
    const { daysInMonth, startingDay, year, month } = getDaysInMonth(currentDate);
    const days = [];
    
    // Add empty cells for days before the first day of the month
    for (let i = 0; i < startingDay; i++) {
      days.push(<div key={`empty-${i}`} className="p-2 text-gray-500"></div>);
    }
    
    // Add days of the month
    for (let day = 1; day <= daysInMonth; day++) {
      const date = new Date(year, month, day);
      const dayEvents = getEventsForDate(date);
      const isToday = date.toDateString() === new Date().toDateString();
      
      days.push(
        <div 
          key={day} 
          className={`p-2 min-h-[100px] border border-gray-700/50 ${
            isToday ? 'bg-blue-900/20 border-blue-500/50' : ''
          }`}
        >
          <div className={`text-sm font-medium ${
            isToday ? 'text-blue-400' : 'text-gray-300'
          }`}>
            {day}
          </div>
          <div className="mt-1 space-y-1">
            {dayEvents.slice(0, 2).map((event, index) => (
              <div
                key={index}
                className="text-xs p-1 bg-red-600/20 border border-red-500/30 rounded truncate cursor-pointer hover:bg-red-600/30"
                title={event.title}
              >
                {event.title}
              </div>
            ))}
            {dayEvents.length > 2 && (
              <div className="text-xs text-gray-400">
                +{dayEvents.length - 2} more
              </div>
            )}
          </div>
        </div>
      );
    }
    
    return (
      <div className="grid grid-cols-7 gap-1">
        {['Sun', 'Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat'].map(day => (
          <div key={day} className="p-2 text-center text-sm font-medium text-gray-400 border-b border-gray-700/50">
            {day}
          </div>
        ))}
        {days}
      </div>
    );
  };

  const renderListView = () => {
    const sortedEvents = [...events].sort((a, b) => new Date(a.start) - new Date(b.start));
    
    return (
      <div className="space-y-4">
        {sortedEvents.length === 0 ? (
          <div className="text-center py-8">
            <FaCalendarAlt className="w-12 h-12 text-gray-500 mx-auto mb-4" />
            <p className="text-gray-400">No events found</p>
          </div>
        ) : (
          sortedEvents.map((event, index) => (
            <div
              key={index}
              className="bg-gray-800/50 backdrop-blur-sm p-4 rounded-lg border border-gray-700/50 hover:border-gray-600/50 transition-all duration-200"
            >
              <div className="flex items-start justify-between">
                <div className="flex-1">
                  <h3 className="text-lg font-semibold text-white mb-2">{event.title}</h3>
                  <div className="space-y-1 text-sm text-gray-400">
                    <div className="flex items-center space-x-2">
                      <span className="text-gray-500">📅</span>
                      <span>{formatDate(event.start)}</span>
                    </div>
                    {event.location && (
                      <div className="flex items-center space-x-2">
                        <span className="text-gray-500">📍</span>
                        <span>{event.location}</span>
                      </div>
                    )}
                    {event.description && (
                      <div className="flex items-start space-x-2">
                        <span className="text-gray-500 mt-1">📝</span>
                        <p className="text-gray-400 line-clamp-2">{event.description}</p>
                      </div>
                    )}
                  </div>
                </div>
                <div className="flex space-x-2">
                  <button
                    onClick={() => window.open(event.jump_url || '#', '_blank')}
                    className="p-2 text-gray-400 hover:text-blue-400 transition-colors"
                    title="Open in Google Calendar"
                  >
                    <FaExternalLinkAlt className="w-4 h-4" />
                  </button>
                </div>
              </div>
            </div>
          ))
        )}
      </div>
    );
  };

  const navigateMonth = (direction) => {
    const newDate = new Date(currentDate);
    newDate.setMonth(newDate.getMonth() + direction);
    setCurrentDate(newDate);
  };

  if (loading) {
    return (
      <OrganizationNavbar>
        <ThemedLoading message="Loading calendar events..." />
      </OrganizationNavbar>
    );
  }

  return (
    <OrganizationNavbar>
      <div className="max-w-7xl mx-auto px-4 py-8">
        {/* Header */}
        <div className="flex items-center justify-between mb-8">
          <div>
            <h1 className="text-3xl font-bold text-white mb-2">Calendar</h1>
            <p className="text-gray-400">
              Events for {currentOrg?.name || 'Your Organization'}
            </p>
          </div>
          
          <div className="flex items-center space-x-4">
            {/* View Mode Toggle */}
            <div className="flex bg-gray-800/50 backdrop-blur-sm rounded-lg border border-gray-700/50">
              <button
                onClick={() => setViewMode('month')}
                className={`px-4 py-2 text-sm font-medium transition-colors ${
                  viewMode === 'month' 
                    ? 'bg-blue-600/50 text-blue-300' 
                    : 'text-gray-400 hover:text-white'
                }`}
              >
                Month
              </button>
              <button
                onClick={() => setViewMode('list')}
                className={`px-4 py-2 text-sm font-medium transition-colors ${
                  viewMode === 'list' 
                    ? 'bg-blue-600/50 text-blue-300' 
                    : 'text-gray-400 hover:text-white'
                }`}
              >
                List
              </button>
            </div>
            
            {/* Refresh Button */}
            <button
              onClick={fetchEvents}
              className="p-2 bg-gray-800/50 backdrop-blur-sm rounded-lg border border-gray-700/50 hover:border-gray-600/50 transition-all duration-200 text-gray-400 hover:text-white"
              title="Refresh events"
            >
              <FaSync className="w-4 h-4" />
            </button>
            
            {/* Settings Button */}
            <button
              onClick={() => window.location.href = `/${currentOrg?.prefix}/calendar/settings`}
              className="p-2 bg-gray-800/50 backdrop-blur-sm rounded-lg border border-gray-700/50 hover:border-gray-600/50 transition-all duration-200 text-gray-400 hover:text-white"
              title="Calendar settings"
            >
              <FaCog className="w-4 h-4" />
            </button>
          </div>
        </div>

        {/* Error Display */}
        {error && (
          <div className="mb-6 p-4 bg-red-900/50 backdrop-blur-sm rounded-lg border border-red-500/50">
            <p className="text-red-300">{error}</p>
          </div>
        )}

        {/* Calendar Navigation (Month View Only) */}
        {viewMode === 'month' && (
          <div className="flex items-center justify-between mb-6">
            <button
              onClick={() => navigateMonth(-1)}
              className="p-2 bg-gray-800/50 backdrop-blur-sm rounded-lg border border-gray-700/50 hover:border-gray-600/50 transition-all duration-200 text-gray-400 hover:text-white"
            >
              ← Previous
            </button>
            
            <h2 className="text-xl font-semibold text-white">
              {currentDate.toLocaleDateString('en-US', { 
                month: 'long', 
                year: 'numeric' 
              })}
            </h2>
            
            <button
              onClick={() => navigateMonth(1)}
              className="p-2 bg-gray-800/50 backdrop-blur-sm rounded-lg border border-gray-700/50 hover:border-gray-600/50 transition-all duration-200 text-gray-400 hover:text-white"
            >
              Next →
            </button>
          </div>
        )}

        {/* Calendar Content */}
        <div className="bg-gray-900/50 backdrop-blur-sm rounded-xl border border-gray-700/50 p-6">
          {viewMode === 'month' ? renderMonthView() : renderListView()}
        </div>

        {/* Event Count */}
        <div className="mt-6 text-center">
          <p className="text-gray-400">
            {events.length} event{events.length !== 1 ? 's' : ''} found
          </p>
        </div>
      </div>
    </OrganizationNavbar>
  );
};

export default Calendar;
