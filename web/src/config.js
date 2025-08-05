// Frontend configuration
const config = {
  // API Base URL - can be overridden by environment variable
  apiUrl: process.env.REACT_APP_API_URL || 'http://localhost:8000',
  
  // Other configuration options
  tokenRefreshInterval: 15 * 60 * 1000, // 15 minutes in milliseconds
  
  // Environment-specific settings
  isDevelopment: process.env.NODE_ENV === 'development',
  isProduction: process.env.NODE_ENV === 'production',
};

export default config; 