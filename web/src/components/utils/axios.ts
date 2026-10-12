import axios, { type InternalAxiosRequestConfig } from "axios";
import type { Organization } from "../../types";
import config from "../../config";

const apiClient = axios.create({
  baseURL: config.apiUrl,
});

// _retry marks a request that the response interceptor sent again after a token refresh.
type RetryConfig = InternalAxiosRequestConfig & { _retry?: boolean };

// Attach token to all requests
apiClient.interceptors.request.use(
  (config) => {
    const token = localStorage.getItem("accessToken");
    if (token) {
      config.headers["Authorization"] = `Bearer ${token}`;
    }

    // Add organization context if available
    const currentOrg: Organization | null = JSON.parse(localStorage.getItem("currentOrg") || "null");
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
    if (!axios.isAxiosError(error) || !error.config) return Promise.reject(error);
    const originalRequest: RetryConfig = error.config;

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
        const response = await axios.post<{ access_token?: string }>(
          `${config.apiUrl}/api/auth/refresh`,
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
      } catch {
        // Refresh failed, clear all tokens and redirect to login
        localStorage.clear();
        window.location.href = "/login";
      }
    }

    return Promise.reject(error);
  }
);

export default apiClient;
