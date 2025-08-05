// src/pages/TokenRetrival.js
import React, { useEffect, useState } from 'react';
import { useNavigate, useLocation } from 'react-router-dom';
import { useAuth } from '../components/auth/AuthContext';
import axios from 'axios';
import config from '../config';

const TokenRetrival = () => {
  const navigate = useNavigate();
  const location = useLocation();
  const { setToken, setRefreshToken, setUser, setOrganizations, setIsSuperAdmin } = useAuth();
  const [status, setStatus] = useState('Processing login...');

  useEffect(() => {
    const handleTokenRetrival = async () => {
      const query = new URLSearchParams(location.search);
      const accessToken = query.get('access_token');
      const refreshToken = query.get('refresh_token');
      const error = query.get('error');

      // Handle error from OAuth callback
      if (error) {
        console.error('OAuth error:', error);
        navigate('/login');
        return;
      }

      // Handle successful OAuth callback with token pair
      if (accessToken && refreshToken) {
        try {
          setStatus('Storing authentication tokens...');
          
          // Store both tokens
          localStorage.setItem('accessToken', accessToken);
          localStorage.setItem('refreshToken', refreshToken);
          setToken(accessToken);
          setRefreshToken(refreshToken);
          
          // Clear URL parameters
          window.history.replaceState({}, document.title, window.location.pathname);
          
          setStatus('Validating authentication...');
          
          // Validate token and get user info
          const userResponse = await axios.get(`${config.apiUrl}/api/auth/name`, {
            headers: { Authorization: `Bearer ${accessToken}` }
          });
          
          if (userResponse.data) {
            setUser(userResponse.data);
            localStorage.setItem('user', JSON.stringify(userResponse.data));
          }
          
          setStatus('Fetching organizations...');
          
          // Get organizations
          const orgsResponse = await axios.get(`${config.apiUrl}/api/organizations/`, {
            headers: { Authorization: `Bearer ${accessToken}` }
          });
          
          setOrganizations(orgsResponse.data || []);
          
          setStatus('Checking permissions...');
          
          // Check superadmin status
          try {
            const superAdminResponse = await axios.get(`${config.apiUrl}/api/superadmin/check`, {
              headers: { Authorization: `Bearer ${accessToken}` }
            });
            setIsSuperAdmin(superAdminResponse.data.is_superadmin);
          } catch (error) {
            // Not a superadmin, that's fine
            setIsSuperAdmin(false);
          }
          
          setStatus('Redirecting...');
          
          // Navigate based on organizations
          if (orgsResponse.data && orgsResponse.data.length > 0) {
            navigate('/select-organization');
          } else {
            navigate('/home');
          }
          
        } catch (error) {
          console.error('Error processing tokens:', error);
          navigate('/login');
        }
      } else {
        // No tokens, redirect to login
        console.error('No tokens received from OAuth callback');
        navigate('/login');
      }
    };

    handleTokenRetrival();
  }, [location, navigate, setToken, setRefreshToken, setUser, setOrganizations, setIsSuperAdmin]);

  return (
    <div className="min-h-screen flex items-center justify-center bg-gray-900 text-white">
      <div className="text-center">
        <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-white mx-auto mb-4"></div>
        <p className="text-lg">Processing login with Discord...</p>
        <p className="text-sm text-gray-400 mt-2">{status}</p>
      </div>
    </div>
  );
};

export default TokenRetrival;
