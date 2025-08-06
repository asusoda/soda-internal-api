import axios from "axios";
import { useAuth } from "../auth/AuthContext";

// Get API base URL from environment or default to localhost for development
const getApiBaseUrl = () => {
  return process.env.REACT_APP_API_URL || "http://localhost:8000";
};

const apiClient = axios.create({
  baseURL: getApiBaseUrl(),
});

// Attach token to all requests
apiClient.interceptors.request.use(
  (config) => {
    const token = localStorage.getItem("accessToken");
    if (token) {
      config.headers["Authorization"] = token;
      config.headers["Authorization"] = `Bearer ${token}`;
    }

    // Add organization context if available
    const currentOrg = JSON.parse(localStorage.getItem("currentOrg") || "null");
    if (currentOrg) {
      config.headers["X-Organization-ID"] = currentOrg.id;
      config.headers["X-Organization-Prefix"] = currentOrg.prefix;
    }

    return config;
  },
  (error) => Promise.reject(error)
);

// Response interceptor to handle token expiration
apiClient.interceptors.response.use(
  (response) => response,
  async (error) => {
    const originalRequest = error.config;

    if (error.response?.status === 403 && !originalRequest._retry) {
      originalRequest._retry = true;

      try {
        const refreshToken = localStorage.getItem("refreshToken");
        if (!refreshToken) {
          // No refresh token, redirect to login
          localStorage.clear();
          window.location.href = "/login";
          return Promise.reject(error);
        }

        // Try to refresh the access token
        const response = await axios.post(
          `${getApiBaseUrl()}/api/auth/refresh`,
          {
            refresh_token: refreshToken,
          }
        );

        if (response.data.access_token) {
          const newToken = response.data.access_token;
          localStorage.setItem("accessToken", newToken);
          originalRequest.headers["Authorization"] = `Bearer ${newToken}`;
          return apiClient(originalRequest);
        }
      } catch (refreshError) {
        // Refresh failed, clear all tokens and redirect to login
        localStorage.clear();
        window.location.href = "/login";
      }
    }

    return Promise.reject(error);
  }
);

export default apiClient;
