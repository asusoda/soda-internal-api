// Frontend configuration
const config = {
  // API Base URL - removes any trailing slash for consistency
  apiUrl: (import.meta.env.REACT_APP_API_URL || 'https://api.thesoda.io').replace(/\/$/, ''),
  tokenRefreshInterval: 15 * 60 * 1000, // 15 minutes in milliseconds
};

export default config; 
