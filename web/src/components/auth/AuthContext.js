import React, { createContext, useContext, useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import axios from 'axios';
import config from '../../config';

const AuthContext = createContext();

export const useAuth = () => {
  const context = useContext(AuthContext);
  if (!context) {
    throw new Error('useAuth must be used within an AuthProvider');
  }
  return context;
};

export const AuthProvider = ({ children }) => {
  const [token, setToken] = useState(localStorage.getItem('accessToken') || null);
  const [refreshToken, setRefreshToken] = useState(localStorage.getItem('refreshToken') || null);
  const [user, setUser] = useState(() => {
    const stored = localStorage.getItem('user');
    return stored ? JSON.parse(stored) : null;
  });
  const [currentOrg, setCurrentOrg] = useState(() => {
    const stored = localStorage.getItem('currentOrg');
    return stored ? JSON.parse(stored) : null;
  });
  const [organizations, setOrganizations] = useState([]);
  const [loading, setLoading] = useState(true);
  const [isSuperAdmin, setIsSuperAdmin] = useState(false);
  const navigate = useNavigate();

  const apiBaseUrl = config.apiUrl;

  // Function to validate token
  const validateToken = async () => {
    if (!token) return false;
    try {
      const response = await axios.get(`${apiBaseUrl}/api/auth/validToken`, {
        headers: { Authorization: `Bearer ${token}` },
      });
      return response.data.valid;
    } catch (error) {
      console.error('Token validation error:', error);
      return false;
    }
  };

  // Function to refresh access token using refresh token
  const refreshAccessToken = async () => {
    if (!refreshToken) return false;
    try {
      const response = await axios.post(`${apiBaseUrl}/api/auth/refresh`, {
        refresh_token: refreshToken
      });
      
      if (response.data.access_token) {
        const newToken = response.data.access_token;
        setToken(newToken);
        localStorage.setItem('accessToken', newToken);
        return true;
      }
      return false;
    } catch (error) {
      console.error('Error refreshing token:', error);
      // If refresh fails, clear all tokens and redirect to login
      logout();
      return false;
    }
  };

  // Function to get user info from token
  const getUserInfo = async () => {
    if (!token) return null;
    try {
      const response = await axios.get(`${apiBaseUrl}/api/auth/name`, {
        headers: { Authorization: `Bearer ${token}` },
      });
      return response.data;
    } catch (error) {
      console.error('Error getting user info:', error);
      return null;
    }
  };

  // Function to fetch user's organizations
  const fetchOrganizations = async () => {
    if (!token) return [];
    try {
      const response = await axios.get(`${apiBaseUrl}/api/organizations/`, {
        headers: { Authorization: `Bearer ${token}` },
      });
      return response.data;
    } catch (error) {
      console.error('Error fetching organizations:', error);
      return [];
    }
  };

  // Function to check if user is superadmin
  const checkSuperAdminStatus = async () => {
    if (!token) {
      return false;
    }
    try {
      const response = await axios.get(`${apiBaseUrl}/api/superadmin/check`, {
        headers: { Authorization: `Bearer ${token}` },
      });
      return response.data.is_superadmin;
    } catch (error) {
      console.error('Error checking superadmin status:', error);
      return false;
    }
  };

  // Function to handle token expiration and auto-refresh
  const handleTokenExpiration = async () => {
    if (refreshToken) {
      const success = await refreshAccessToken();
      if (success) {
        return true;
      }
    }
    // If refresh fails, logout
    logout();
    return false;
  };

  // Function to make authenticated API calls with auto-refresh
  const makeAuthenticatedRequest = async (apiCall) => {
    try {
      return await apiCall();
    } catch (error) {
      if (error.response && error.response.status === 403) {
        // Token expired, try to refresh
        const refreshed = await handleTokenExpiration();
        if (refreshed) {
          // Retry the original request with new token
          return await apiCall();
        }
      }
      throw error;
    }
  };

  const selectOrganization = (org) => {
    setCurrentOrg(org);
    localStorage.setItem('currentOrg', JSON.stringify(org));
  };

  const logout = async () => {
    try {
      // Revoke refresh token if available
      if (refreshToken) {
        await axios.post(`${apiBaseUrl}/api/auth/logout`, {
          refresh_token: refreshToken
        }, {
          headers: { Authorization: `Bearer ${token}` }
        });
      }
    } catch (error) {
      console.error('Error during logout:', error);
    } finally {
      // Clear all local storage and state
      localStorage.removeItem('accessToken');
      localStorage.removeItem('refreshToken');
      localStorage.removeItem('user');
      localStorage.removeItem('currentOrg');
      setToken(null);
      setRefreshToken(null);
      setUser(null);
      setCurrentOrg(null);
      setOrganizations([]);
      setIsSuperAdmin(false);
      navigate('/login');
    }
  };

  const getApiClient = () => {
    const client = axios.create({
      baseURL: apiBaseUrl,
      headers: {
        'Content-Type': 'application/json',
      },
    });

    // Add request interceptor to include token
    client.interceptors.request.use(
      (config) => {
        if (token) {
          config.headers.Authorization = `Bearer ${token}`;
        }
        return config;
      },
      (error) => {
        return Promise.reject(error);
      }
    );

    // Add response interceptor to handle token expiration
    client.interceptors.response.use(
      (response) => response,
      async (error) => {
        if (error.response && error.response.status === 403) {
          const refreshed = await handleTokenExpiration();
          if (refreshed) {
            // Retry the original request
            error.config.headers.Authorization = `Bearer ${token}`;
            return client.request(error.config);
          }
        }
        return Promise.reject(error);
      }
    );

    return client;
  };

  useEffect(() => {
    const authenticateUser = async () => {
      setLoading(true);
      try {
        // Only proceed if we have a token
        if (!token) {
          setLoading(false);
          return;
        }

        // Validate current token
        const isValid = await validateToken();
        if (!isValid) {
          // Try to refresh token
          const refreshed = await refreshAccessToken();
          if (!refreshed) {
            logout();
            return;
          }
        }

        // Get user info and organizations
        const userInfo = await getUserInfo();
        if (userInfo) {
          setUser(userInfo);
          localStorage.setItem('user', JSON.stringify(userInfo));
        }

        const orgs = await fetchOrganizations();
        setOrganizations(orgs);

        // Check superadmin status
        const superAdminStatus = await checkSuperAdminStatus();
        setIsSuperAdmin(superAdminStatus);

      } catch (error) {
        console.error('Authentication error:', error);
        logout();
      } finally {
        setLoading(false);
      }
    };

    authenticateUser();
  }, [token]);

  const value = {
    token,
    refreshToken,
    user,
    currentOrg,
    organizations,
    loading,
    isSuperAdmin,
    login: () => window.location.href = `${apiBaseUrl}/api/auth/login`,
    logout,
    selectOrganization,
    getApiClient,
    makeAuthenticatedRequest,
    refreshAccessToken,
    validateToken,
    setToken,
    setRefreshToken,
    setUser,
    setOrganizations,
    setIsSuperAdmin,
  };

  return (
    <AuthContext.Provider value={value}>
      {children}
    </AuthContext.Provider>
  );
};
