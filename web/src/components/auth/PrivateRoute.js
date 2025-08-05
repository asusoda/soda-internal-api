import React from 'react';
import { Navigate, useParams } from 'react-router-dom';
import { useAuth } from './AuthContext';
import ThemedLoading from '../ui/ThemedLoading';

const PrivateRoute = ({ children }) => {
  const { token, currentOrg, organizations, loading } = useAuth();
  const { orgPrefix } = useParams();
  
  console.log('PrivateRoute: Checking access', { 
    token: !!token, 
    loading, 
    orgPrefix, 
    currentOrg: currentOrg?.prefix,
    orgsCount: organizations.length,
    currentPath: window.location.pathname
  });
  
  // Show loading while authentication is in progress
  if (loading) {
    console.log('PrivateRoute: Still loading, showing loading screen');
    return <ThemedLoading message="Authenticating..." />;
  }
  
  // Redirect to login if no token
  if (!token) {
    console.log('PrivateRoute: No token, redirecting to login');
    return <Navigate to="/" />;
  }

  // If route has orgPrefix parameter, validate organization access
  if (orgPrefix) {
    console.log('PrivateRoute: Route has orgPrefix, validating access');
    // Check if user has access to the requested organization
    const requestedOrg = organizations.find(org => org.prefix === orgPrefix);
    
    if (!requestedOrg) {
      console.log('PrivateRoute: User does not have access to requested org, redirecting to select-organization');
      // User doesn't have access to this organization
      return <Navigate to="/select-organization" />;
    }

    // If current org doesn't match the requested org, update it
    if (!currentOrg || currentOrg.prefix !== orgPrefix) {
      console.log('PrivateRoute: Current org does not match requested org, redirecting to select-organization');
      // This will be handled by the AuthContext when the org is selected
      return <Navigate to="/select-organization" />;
    }
  } else {
    // If no orgPrefix in route but user has organizations, redirect to org selection
    // Always redirect if no currentOrg is selected, regardless of localStorage
    const currentPath = window.location.pathname;
    const specialPaths = ['/select-organization', '/auth', '/500', '/superadmin'];
    
    console.log('PrivateRoute: No orgPrefix in route, checking redirect conditions', {
      hasOrgs: organizations.length > 0,
      hasCurrentOrg: !!currentOrg,
      isSpecialPath: specialPaths.includes(currentPath),
      shouldRedirect: organizations.length > 0 && !currentOrg && !specialPaths.includes(currentPath)
    });
    
    if (organizations.length > 0 && !currentOrg && !specialPaths.includes(currentPath)) {
      console.log('PrivateRoute: User has orgs but no current org selected, redirecting to select-organization');
      return <Navigate to="/select-organization" />;
    }
  }

  console.log('PrivateRoute: Access granted, rendering children');
  return children;
};

export default PrivateRoute;
