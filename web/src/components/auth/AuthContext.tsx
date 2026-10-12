import { createContext, useContext, useState, useEffect, type Dispatch, type ReactNode, type SetStateAction } from 'react';
import { useNavigate } from 'react-router-dom';
import axios, { type AxiosInstance } from 'axios';
import config from '../../config';
import useLatestRef from '../../hooks/useLatestRef';
import type { AuthUser, Organization } from '../../types';

export interface AuthContextValue {
  token: string | null;
  refreshToken: string | null;
  user: AuthUser | null;
  currentOrg: Organization | null;
  organizations: Organization[];
  loading: boolean;
  isSuperAdmin: boolean;
  login: () => void;
  logout: () => Promise<void>;
  selectOrganization: (org: Organization) => void;
  getApiClient: () => AxiosInstance;
  makeAuthenticatedRequest: <T>(apiCall: () => Promise<T>) => Promise<T>;
  refreshAccessToken: () => Promise<boolean>;
  validateToken: () => Promise<boolean>;
  setToken: Dispatch<SetStateAction<string | null>>;
  setRefreshToken: Dispatch<SetStateAction<string | null>>;
  setUser: Dispatch<SetStateAction<AuthUser | null>>;
  setOrganizations: Dispatch<SetStateAction<Organization[]>>;
  setIsSuperAdmin: Dispatch<SetStateAction<boolean>>;
}

const AuthContext = createContext<AuthContextValue | null>(null);

export const useAuth = () => {
  const context = useContext(AuthContext);
  if (!context) {
    throw new Error('useAuth must be used within an AuthProvider');
  }
  return context;
};

export const AuthProvider = ({ children }: { children: ReactNode }) => {
  const [token, setToken] = useState<string | null>(localStorage.getItem('accessToken') || null);
  const [refreshToken, setRefreshToken] = useState<string | null>(localStorage.getItem('refreshToken') || null);
  const [user, setUser] = useState<AuthUser | null>(() => {
    const stored = localStorage.getItem('user');
    return stored ? JSON.parse(stored) : null;
  });
  const [currentOrg, setCurrentOrg] = useState<Organization | null>(() => {
    const stored = localStorage.getItem('currentOrg');
    return stored ? JSON.parse(stored) : null;
  });
  const [organizations, setOrganizations] = useState<Organization[]>([]);
  const [loading, setLoading] = useState(true);
  const [isSuperAdmin, setIsSuperAdmin] = useState(false);
  const navigate = useNavigate();


  // Function to validate token
  const validateToken = async (): Promise<boolean> => {
    if (!token) return false;
    try {
      const response = await axios.get<{ valid: boolean }>(`${config.apiUrl}/api/auth/validToken`, {
        headers: { Authorization: `Bearer ${token}` },
      });
      return response.data.valid;
    } catch (error) {
      console.error('Token validation error:', error);
      return false;
    }
  };

  // Function to refresh access token using refresh token
  const refreshAccessToken = async (): Promise<boolean> => {
    if (!refreshToken) return false;
    try {
      const response = await axios.post<{ access_token?: string }>(`${config.apiUrl}/api/auth/refresh`, {
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
  const getUserInfo = async (): Promise<AuthUser | null> => {
    if (!token) return null;
    try {
      const response = await axios.get<AuthUser>(`${config.apiUrl}/api/auth/name`, {
        headers: { Authorization: `Bearer ${token}` },
      });
      return response.data;
    } catch (error) {
      console.error('Error getting user info:', error);
      return null;
    }
  };

  // Function to fetch user's organizations
  const fetchOrganizations = async (): Promise<Organization[]> => {
    if (!token) return [];
    try {
      const response = await axios.get<Organization[]>(`${config.apiUrl}/api/organizations/`, {
        headers: { Authorization: `Bearer ${token}` },
      });
      return response.data;
    } catch (error) {
      console.error('Error fetching organizations:', error);
      return [];
    }
  };

  // Function to check if user is superadmin
  const checkSuperAdminStatus = async (): Promise<boolean> => {
    if (!token) {
      return false;
    }
    try {
      const response = await axios.get<{ is_superadmin: boolean }>(`${config.apiUrl}/api/superadmin/check`, {
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
  const makeAuthenticatedRequest = async <T,>(apiCall: () => Promise<T>): Promise<T> => {
    try {
      return await apiCall();
    } catch (error) {
      if (axios.isAxiosError(error) && error.response?.status === 403) {
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

  const selectOrganization = (org: Organization) => {
    setCurrentOrg(org);
    localStorage.setItem('currentOrg', JSON.stringify(org));
  };

  const logout = async (): Promise<void> => {
    try {
      // Revoke refresh token if available
      if (refreshToken) {
        await axios.post(`${config.apiUrl}/api/auth/logout`, {
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

  const getApiClient = (): AxiosInstance => {
    const client = axios.create({
      baseURL: config.apiUrl,
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
        if (axios.isAxiosError(error) && error.response?.status === 403 && error.config) {
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

  // The helpers above are new functions on each render. The effect below uses the
  // latest ones through this ref, so that it runs only when the token changes.
  const authHelpersRef = useLatestRef({
    validateToken,
    refreshAccessToken,
    logout,
    getUserInfo,
    fetchOrganizations,
    checkSuperAdminStatus,
  });

  useEffect(() => {
    const {
      validateToken,
      refreshAccessToken,
      logout,
      getUserInfo,
      fetchOrganizations,
      checkSuperAdminStatus,
    } = authHelpersRef.current;

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
  }, [token, authHelpersRef]);

  const value: AuthContextValue = {
    token,
    refreshToken,
    user,
    currentOrg,
    organizations,
    loading,
    isSuperAdmin,
    login: () => window.location.href = `${config.apiUrl}/api/auth/login`,
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
