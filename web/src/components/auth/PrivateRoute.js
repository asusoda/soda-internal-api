import React from 'react';
import { Navigate } from 'react-router-dom';
import { useAuth } from '../auth/AuthContext';

const PrivateRoute = ({ children }) => {
  const { token } = useAuth();
  
  // Redirect to login if no token
  return token ? children : <Navigate to="/" />;
};

export default PrivateRoute;
