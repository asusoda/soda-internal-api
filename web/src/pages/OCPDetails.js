import React, { useState, useEffect } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import {
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TableRow,
  Paper,
  Typography,
  Box,
  Card,
  CardContent,
  Grid,
  CircularProgress,
  Alert,
  Button,
  Collapse,
  IconButton,
  Divider,
  Chip,
  Snackbar,
  createTheme,
  ThemeProvider
} from '@mui/material';
import RefreshIcon from '@mui/icons-material/Refresh';
import SyncIcon from '@mui/icons-material/Sync';

// Create a dark theme
const darkTheme = createTheme({
  palette: {
    mode: 'dark',
    primary: {
      main: '#90caf9',
    },
    secondary: {
      main: '#f48fb1',
    },
    background: {
      default: '#121212',
      paper: '#1e1e1e',
    },
  },
});

const OCPDetails = () => {
  const { officerId } = useParams();
  const navigate = useNavigate();
  const [expandedOfficer, setExpandedOfficer] = useState(null);
  
  // State for officers leaderboard
  const [leaderboard, setLeaderboard] = useState([]);
  const [leaderboardLoading, setLeaderboardLoading] = useState(true);
  
  // State for all events
  const [allEvents, setAllEvents] = useState([]);
  const [eventsLoading, setEventsLoading] = useState(true);
  
  // State for sync notification
  const [syncNotification, setSyncNotification] = useState({
    open: false,
    message: '',
    severity: 'info'
  });
  const [syncing, setSyncing] = useState(false);
  const [error, setError] = useState(null);
  
  // Add state for diagnostic operations
  const [diagnosingOfficers, setDiagnosingOfficers] = useState(false);
  const [fixingOfficers, setFixingOfficers] = useState(false);
  const [debugSyncing, setDebugSyncing] = useState(false);
  const [diagnosticResults, setDiagnosticResults] = useState(null);

  // Fetch officer leaderboard and all events on component mount
  useEffect(() => {
    const fetchInitialData = async () => {
      try {
        // Fetch leaderboard
        const leaderboardResponse = await fetch('http://localhost:8000/calendar/ocp/officers');
        const leaderboardData = await leaderboardResponse.json();
        
        if (leaderboardData.status === 'success') {
          setLeaderboard(leaderboardData.officers);
        } else {
          console.error('Error fetching leaderboard:', leaderboardData.message);
        }
        
        // Also fetch all events at the same time
        fetchAllEvents();
      } catch (err) {
        console.error('Error fetching initial data:', err);
      } finally {
        setLeaderboardLoading(false);
      }
    };
    
    fetchInitialData();
  }, []);

  const fetchAllEvents = async () => {
    console.log("Fetching all events from /calendar/ocp/events endpoint");
    setEventsLoading(true);
    try {
      // Use the dedicated endpoint to fetch all events
      const response = await fetch('http://localhost:8000/calendar/ocp/events');
      
      if (!response.ok) {
        throw new Error(`Server responded with status: ${response.status}`);
      }
      
      const data = await response.json();
      
      console.log("Events response:", data);
      
      if (data.status === 'success' && Array.isArray(data.events)) {
        // Process the events to the format expected by the component
        const processedEvents = data.events.map(event => ({
          ...event,
          officer_name: event.officer?.name || 'Unknown',
          officer_department: event.officer?.department || 'Unknown',
          officer_title: event.officer?.title || 'Unknown'
        }));
        
        console.log("Processed events:", processedEvents);
        setAllEvents(processedEvents);
      } else {
        console.error('Error fetching events:', data.message || 'Invalid response format');
        setError(`Failed to fetch events: ${data.message || 'Invalid response format'}`);
      }
    } catch (err) {
      console.error('Error fetching all events:', err);
      setError(`Error fetching events: ${err.message}`);
    } finally {
      setEventsLoading(false);
    }
  };
  
  // Function to trigger Notion sync
  const syncWithNotion = async () => {
    setSyncing(true);
    try {
      const response = await fetch('http://localhost:8000/calendar/ocp/sync-from-notion', {
        method: 'POST'
      });
      
      const data = await response.json();
      
      if (data.status === 'success') {
        setSyncNotification({
          open: true,
          message: `Sync completed successfully! Added ${data.added_points_count || 0} new points, updated ${data.updated_points_count || 0} existing records.`,
          severity: 'success'
        });
        
        // Refresh data after successful sync
        // Refresh leaderboard
        const leaderboardResponse = await fetch('http://localhost:8000/calendar/ocp/officers');
        const leaderboardData = await leaderboardResponse.json();
        if (leaderboardData.status === 'success') {
          setLeaderboard(leaderboardData.officers);
        }
        
        // Refresh events
        fetchAllEvents();
      } else if (data.status === 'warning') {
        setSyncNotification({
          open: true,
          message: data.message || 'Sync completed with warnings.',
          severity: 'warning'
        });
      } else {
        setSyncNotification({
          open: true,
          message: data.message || 'Error synchronizing with Notion.',
          severity: 'error'
        });
      }
    } catch (err) {
      console.error('Error syncing with Notion:', err);
      setSyncNotification({
        open: true,
        message: 'Failed to connect to the server for Notion sync.',
        severity: 'error'
      });
    } finally {
      setSyncing(false);
    }
  };

  // Function for Debug Sync with Notion
  const debugSyncWithNotion = async () => {
    setDebugSyncing(true);
    setDiagnosticResults(null);
    try {
      const response = await fetch('http://localhost:8000/calendar/ocp/debug-sync-from-notion', {
        method: 'POST'
      });
      
      const data = await response.json();
      
      setDiagnosticResults({
        title: 'Debug Sync Results',
        message: `Debug sync completed with status: ${data.status}. ${data.message || ''}`,
        details: data
      });
      
      // Refresh data after sync
      fetchAllEvents();
      const leaderboardResponse = await fetch('http://localhost:8000/calendar/ocp/officers');
      const leaderboardData = await leaderboardResponse.json();
      if (leaderboardData.status === 'success') {
        setLeaderboard(leaderboardData.officers);
      }
      
      setSyncNotification({
        open: true,
        message: `Debug sync completed with status: ${data.status}. Check server logs for details.`,
        severity: data.status === 'success' ? 'success' : data.status === 'warning' ? 'warning' : 'error'
      });
    } catch (err) {
      console.error('Error during debug sync:', err);
      setSyncNotification({
        open: true,
        message: 'Error during debug sync. Check console for details.',
        severity: 'error'
      });
    } finally {
      setDebugSyncing(false);
    }
  };
  
  // Function to diagnose unknown officers
  const diagnoseUnknownOfficers = async () => {
    setDiagnosingOfficers(true);
    setDiagnosticResults(null);
    try {
      // First try with GET request
      let response;
      try {
        response = await fetch('http://localhost:8000/calendar/ocp/diagnose-unknown-officers');
        
        // If GET fails with 404, try with POST
        if (response.status === 404) {
          console.log("GET request failed with 404, trying POST instead");
          response = await fetch('http://localhost:8000/calendar/ocp/diagnose-unknown-officers', {
            method: 'POST'
          });
        }
      } catch (fetchError) {
        console.log("GET request failed, trying POST as fallback");
        response = await fetch('http://localhost:8000/calendar/ocp/diagnose-unknown-officers', {
          method: 'POST'
        });
      }
      
      const data = await response.json();
      
      setDiagnosticResults({
        title: 'Officer Diagnosis Results',
        message: `Found ${data.total_issues || 0} issues: ${data.missing_uuid_count || 0} missing UUIDs and ${data.unknown_name_count || 0} unknown officer names. (Department/email issues are ignored)`,
        details: data
      });
      
      setSyncNotification({
        open: true,
        message: `Officer diagnosis completed. Found ${data.total_issues || 0} issues. Check server logs for details.`,
        severity: 'info'
      });
    } catch (err) {
      console.error('Error diagnosing officers:', err);
      setSyncNotification({
        open: true,
        message: 'Error diagnosing officers. Check console for details.',
        severity: 'error'
      });
    } finally {
      setDiagnosingOfficers(false);
    }
  };
  
  // Function to fix unknown officers
  const fixUnknownOfficers = async () => {
    setFixingOfficers(true);
    setDiagnosticResults(null);
    try {
      const response = await fetch('http://localhost:8000/calendar/ocp/repair-officers', {
        method: 'POST'
      });
      
      const data = await response.json();
      
      setDiagnosticResults({
        title: 'Officer Repair Results',
        message: data.message || 'Repair completed',
        details: data
      });
      
      // Refresh data after repair
      fetchAllEvents();
      const leaderboardResponse = await fetch('http://localhost:8000/calendar/ocp/officers');
      const leaderboardData = await leaderboardResponse.json();
      if (leaderboardData.status === 'success') {
        setLeaderboard(leaderboardData.officers);
      }
      
      setSyncNotification({
        open: true,
        message: data.message || 'Officer repair completed.',
        severity: data.status === 'success' ? 'success' : 'error'
      });
    } catch (err) {
      console.error('Error fixing officers:', err);
      setSyncNotification({
        open: true,
        message: 'Error fixing officers. Check console for details.',
        severity: 'error'
      });
    } finally {
      setFixingOfficers(false);
    }
  };

  // Fetch contributions for a specific officer when expanded
  const fetchOfficerContributions = async (officerId) => {
    if (!officerId) return;
    
    try {
      const response = await fetch(`http://localhost:8000/calendar/ocp/officer/${officerId}/contributions`);
      const data = await response.json();
      
      if (data.status === 'success') {
        // Update the leaderboard with contributions data for this officer
        setLeaderboard(prevLeaderboard => {
          return prevLeaderboard.map(officer => {
            if (officer.uuid === officerId || officer.email === officerId) {
              return { ...officer, contributions: data.contributions };
            }
            return officer;
          });
        });
      }
    } catch (err) {
      console.error('Error fetching officer contributions:', err);
    }
  };

  const handleOfficerClick = (officer) => {
    if (expandedOfficer === officer.uuid) {
      setExpandedOfficer(null);
    } else {
      setExpandedOfficer(officer.uuid);
      fetchOfficerContributions(officer.uuid);
    }
  };
  
  const handleCloseNotification = () => {
    setSyncNotification({
      ...syncNotification,
      open: false
    });
  };

  const formatDate = (dateString) => {
    if (!dateString) return 'N/A';
    return new Date(dateString).toLocaleDateString();
  };

  // Render loading state
  if (leaderboardLoading) {
    return (
      <ThemeProvider theme={darkTheme}>
        <Box 
          display="flex" 
          justifyContent="center" 
          alignItems="center" 
          minHeight="80vh" 
          bgcolor="background.default"
        >
          <CircularProgress />
        </Box>
      </ThemeProvider>
    );
  }

  return (
    <ThemeProvider theme={darkTheme}>
      <Box p={3} bgcolor="background.default" minHeight="100vh">
        <Box display="flex" justifyContent="space-between" alignItems="center" mb={2}>
          <Typography variant="h4" color="text.primary">
            Officer Contribution Points
          </Typography>
          <Box>
            <Button
              variant="contained"
              color="primary"
              startIcon={<SyncIcon />}
              onClick={syncWithNotion}
              disabled={syncing || debugSyncing || diagnosingOfficers || fixingOfficers}
              sx={{ mr: 1 }}
            >
              {syncing ? 'Syncing...' : 'Sync with Notion'}
            </Button>
            
            <Button
              variant="outlined"
              color="info"
              onClick={debugSyncWithNotion}
              disabled={syncing || debugSyncing || diagnosingOfficers || fixingOfficers}
              sx={{ mr: 1 }}
            >
              {debugSyncing ? 'Debug Syncing...' : 'Debug Sync'}
            </Button>
            
            <Button
              variant="outlined"
              color="warning"
              onClick={diagnoseUnknownOfficers}
              disabled={syncing || debugSyncing || diagnosingOfficers || fixingOfficers}
              sx={{ mr: 1 }}
            >
              {diagnosingOfficers ? 'Diagnosing...' : 'Find Missing Officer Names'}
            </Button>
            
            <Button
              variant="outlined"
              color="success"
              onClick={fixUnknownOfficers}
              disabled={syncing || debugSyncing || diagnosingOfficers || fixingOfficers}
            >
              {fixingOfficers ? 'Fixing...' : 'Fix Missing Officer Names'}
            </Button>
          </Box>
        </Box>
        
        {/* Diagnostic Results Display */}
        {diagnosticResults && (
          <Box mt={2} mb={4}>
            <Paper sx={{ p: 2, bgcolor: 'background.paper', boxShadow: 3 }}>
              <Typography variant="h6" gutterBottom>
                {diagnosticResults.title}
              </Typography>
              <Typography variant="body1" paragraph>
                {diagnosticResults.message}
              </Typography>
              {diagnosticResults.details && (
                <Box mt={2}>
                  <Typography variant="subtitle2" color="text.secondary">
                    Check server logs for detailed information
                  </Typography>
                </Box>
              )}
            </Paper>
          </Box>
        )}
        
        <Divider sx={{ mb: 4 }} />

        {/* Section 1: Officers Leaderboard */}
        <Typography variant="h5" color="primary" gutterBottom>
          Officers Leaderboard
        </Typography>
        
        <Box mb={6}>
          <TableContainer 
            component={Paper} 
            sx={{ 
              maxHeight: 500,
              bgcolor: 'background.paper',
              boxShadow: 3,
              mb: 2
            }}
          >
            <Table stickyHeader>
              <TableHead>
                <TableRow>
                  <TableCell>Name</TableCell>
                  <TableCell>Email</TableCell>
                  <TableCell>Title</TableCell>
                  <TableCell>Department</TableCell>
                  <TableCell>Total Points</TableCell>
                  <TableCell>Actions</TableCell>
                </TableRow>
              </TableHead>
              <TableBody>
                {leaderboard.map((officer) => (
                  <React.Fragment key={officer.uuid}>
                    <TableRow>
                      <TableCell>{officer.name}</TableCell>
                      <TableCell>{officer.email || 'N/A'}</TableCell>
                      <TableCell>{officer.title}</TableCell>
                      <TableCell>{officer.department}</TableCell>
                      <TableCell>{officer.total_points}</TableCell>
                      <TableCell>
                        <Button 
                          variant="outlined" 
                          size="small"
                          onClick={() => handleOfficerClick(officer)}
                        >
                          {expandedOfficer === officer.uuid ? 'Hide Events' : 'Show Events'}
                        </Button>
                      </TableCell>
                    </TableRow>
                    {/* Expanded view for officer events */}
                    {expandedOfficer === officer.uuid && officer.contributions && (
                      <TableRow>
                        <TableCell colSpan={6} style={{ paddingTop: 0, paddingBottom: 0 }}>
                          <Collapse in={true} timeout="auto" unmountOnExit>
                            <Box sx={{ margin: 2 }}>
                              <Typography variant="h6" gutterBottom component="div">
                                Events Attended
                              </Typography>
                              <Table size="small">
                                <TableHead>
                                  <TableRow>
                                    <TableCell>Event</TableCell>
                                    <TableCell>Type</TableCell>
                                    <TableCell>Role</TableCell>
                                    <TableCell>Points</TableCell>
                                    <TableCell>Date</TableCell>
                                  </TableRow>
                                </TableHead>
                                <TableBody>
                                  {officer.contributions.map((event) => (
                                    <TableRow key={event.id}>
                                      <TableCell>{event.event}</TableCell>
                                      <TableCell>{event.event_type || 'Other'}</TableCell>
                                      <TableCell>{event.role}</TableCell>
                                      <TableCell>{event.points}</TableCell>
                                      <TableCell>{formatDate(event.timestamp)}</TableCell>
                                    </TableRow>
                                  ))}
                                  {officer.contributions.length === 0 && (
                                    <TableRow>
                                      <TableCell colSpan={5} align="center">No events found</TableCell>
                                    </TableRow>
                                  )}
                                </TableBody>
                              </Table>
                            </Box>
                          </Collapse>
                        </TableCell>
                      </TableRow>
                    )}
                  </React.Fragment>
                ))}
              </TableBody>
            </Table>
          </TableContainer>
        </Box>

        <Divider sx={{ my: 4 }} />

        {/* Section 2: All Events */}
        <Box display="flex" justifyContent="space-between" alignItems="center" mb={2}>
          <Typography variant="h5" color="primary" gutterBottom>
            All Events from All Officers
          </Typography>
          <Button
            variant="contained"
            color="primary"
            startIcon={<RefreshIcon />}
            onClick={fetchAllEvents}
            disabled={eventsLoading}
          >
            Refresh Events
          </Button>
        </Box>
        
        {error && (
          <Alert severity="error" sx={{ mb: 2 }}>
            {error}
            <Button 
              size="small" 
              color="inherit" 
              sx={{ ml: 2 }} 
              onClick={fetchAllEvents}
            >
              Retry
            </Button>
          </Alert>
        )}
        
        {eventsLoading ? (
          <Box display="flex" justifyContent="center" alignItems="center" height="200px">
            <CircularProgress />
          </Box>
        ) : (
          <>
            {/* Events Summary Cards */}
            {allEvents.length > 0 && (
              <Box mb={4}>
                <Grid container spacing={3}>
                  <Grid item xs={12} sm={6} md={3}>
                    <Card sx={{ bgcolor: 'background.paper', boxShadow: 3 }}>
                      <CardContent>
                        <Typography variant="h6" color="text.secondary" gutterBottom>
                          Total Events
                        </Typography>
                        <Typography variant="h4">
                          {allEvents.length}
                        </Typography>
                      </CardContent>
                    </Card>
                  </Grid>
                  <Grid item xs={12} sm={6} md={3}>
                    <Card sx={{ bgcolor: 'background.paper', boxShadow: 3 }}>
                      <CardContent>
                        <Typography variant="h6" color="text.secondary" gutterBottom>
                          Total Points
                        </Typography>
                        <Typography variant="h4">
                          {allEvents.reduce((sum, event) => sum + event.points, 0)}
                        </Typography>
                      </CardContent>
                    </Card>
                  </Grid>
                  <Grid item xs={12} sm={6} md={3}>
                    <Card sx={{ bgcolor: 'background.paper', boxShadow: 3 }}>
                      <CardContent>
                        <Typography variant="h6" color="text.secondary" gutterBottom>
                          Event Types
                        </Typography>
                        <Typography variant="h4">
                          {new Set(allEvents.map(event => event.event_type || 'Other')).size}
                        </Typography>
                      </CardContent>
                    </Card>
                  </Grid>
                  <Grid item xs={12} sm={6} md={3}>
                    <Card sx={{ bgcolor: 'background.paper', boxShadow: 3 }}>
                      <CardContent>
                        <Typography variant="h6" color="text.secondary" gutterBottom>
                          Officers Involved
                        </Typography>
                        <Typography variant="h4">
                          {new Set(allEvents.map(event => event.officer?.uuid || 'unknown')).size}
                        </Typography>
                      </CardContent>
                    </Card>
                  </Grid>
                </Grid>
              </Box>
            )}

            {/* Events Table */}
            <TableContainer 
              component={Paper} 
              sx={{ 
                maxHeight: 600, 
                bgcolor: 'background.paper',
                boxShadow: 3
              }}
            >
              <Table stickyHeader>
                <TableHead>
                  <TableRow>
                    <TableCell>Event</TableCell>
                    <TableCell>Type</TableCell>
                    <TableCell>Role</TableCell>
                    <TableCell>Points</TableCell>
                    <TableCell>Date</TableCell>
                    <TableCell>Officer</TableCell>
                    <TableCell>Department</TableCell>
                    <TableCell>Notion Page</TableCell>
                  </TableRow>
                </TableHead>
                <TableBody>
                  {allEvents.length > 0 ? (
                    allEvents.map((event) => (
                      <TableRow key={event.id}>
                        <TableCell>{event.event}</TableCell>
                        <TableCell>
                          <Chip 
                            label={event.event_type || 'Other'} 
                            size="small" 
                            color={
                              event.event_type === 'GBM' ? 'primary' :
                              event.event_type === 'Special Event' ? 'secondary' :
                              event.event_type === 'Special Contribution' ? 'success' :
                              'default'
                            }
                            variant="outlined"
                          />
                        </TableCell>
                        <TableCell>{event.role}</TableCell>
                        <TableCell>{event.points}</TableCell>
                        <TableCell>{formatDate(event.timestamp)}</TableCell>
                        <TableCell>{event.officer_name}</TableCell>
                        <TableCell>{event.officer_department}</TableCell>
                        <TableCell>
                          {event.notion_page_id ? (
                            <Button 
                              size="small" 
                              variant="text"
                              href={`https://notion.so/${event.notion_page_id.replace(/-/g, '')}`}
                              target="_blank"
                              rel="noopener noreferrer"
                            >
                              View
                            </Button>
                          ) : (
                            <Typography variant="caption" color="text.secondary">
                              N/A
                            </Typography>
                          )}
                        </TableCell>
                      </TableRow>
                    ))
                  ) : (
                    <TableRow>
                      <TableCell colSpan={8} align="center">No events found</TableCell>
                    </TableRow>
                  )}
                </TableBody>
              </Table>
            </TableContainer>
          </>
        )}
      
        {/* Notification for sync status */}
        <Snackbar
          open={syncNotification.open}
          autoHideDuration={6000}
          onClose={handleCloseNotification}
          anchorOrigin={{ vertical: 'bottom', horizontal: 'right' }}
        >
          <Alert 
            onClose={handleCloseNotification} 
            severity={syncNotification.severity}
            variant="filled"
          >
            {syncNotification.message}
          </Alert>
        </Snackbar>
      </Box>
    </ThemeProvider>
  );
};

export default OCPDetails; 