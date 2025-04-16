import React, { createContext, useState, useEffect, useContext } from 'react';
import { useNavigate } from 'react-router-dom';
import axios from 'axios';

// Create the Auth context
const AuthContext = createContext();

export const useAuth = () => {
  return useContext(AuthContext);
};

export const AuthProvider = ({ children }) => {
  const [token, setToken] = useState(localStorage.getItem('accessToken') || null);
  const [loading, setLoading] = useState(true);
  const navigate = useNavigate();

  // Function to validate the token
  const validateToken = async () => {
    if (!token) return false;
    try {
      const response = await axios.get('http://localhost:5000/auth/validToken', {
        headers: { Authorization: token },
      });
      const data = response.data;

      if (data.valid && !data.expired) {
        return true; // Token is valid and not expired
      } else if (data.valid && data.expired) {
        return await refreshToken(); // Token is valid but expired, refresh it
      } else {
        return false;
      }
    } catch (error) {
      console.error('Error validating token:', error);
      return false;
    }
  };

  // Function to refresh the token
  const refreshToken = async () => {
    try {
      const response = await axios.get('http://localhost:5000/auth/refresh', {
        headers: { Authorization: token },
      });
      const data = response.data;

      if (data.valid && data.token) {
        const newToken = `Bearer ${data.token}`;
        setToken(newToken);
        localStorage.setItem('accessToken', newToken);
        return true;
      } else {
        return false;
      }
    } catch (error) {
      console.error('Error refreshing token:', error);
      return false;
    }
  };

  // Function to handle logout
  const logout = () => {
    localStorage.removeItem('accessToken');
    setToken(null);
    navigate('/'); // Redirect to login page
  };

  // Validate the token on initial load
  useEffect(() => {
    const authenticateUser = async () => {
      const isValid = await validateToken();
      if (!isValid) {
        logout();
      }
      setLoading(false);
    };
    authenticateUser();
  }, [token]);

  return (
    <AuthContext.Provider value={{ token, setToken, logout }}>
      {!loading ? children : <div>Loading...</div>}
    </AuthContext.Provider>
  );
};
