import { useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { useAuth } from '../components/auth/AuthContext';

const useAuthToken = () => {
  const navigate = useNavigate();
  const { validateToken, logout } = useAuth();

  // Function to validate and refresh the token using the auth context
  const validateAndRefreshToken = async () => {
    const token = localStorage.getItem('accessToken');
    if (!token) {
      navigate('/');  // Redirect to login page if no token
      return;
    }

    try {
      const isValid = await validateToken();
      if (!isValid) {
        logout(); // This will handle cleanup and redirect
      }
    } catch (error) {
      console.error('Error validating token:', error);
      logout(); // This will handle cleanup and redirect
    }
  };

  useEffect(() => {
    validateAndRefreshToken();  // Initial token validation

    const intervalId = setInterval(validateAndRefreshToken, 900000);  // 15 minutes

    return () => clearInterval(intervalId);  // Clear interval on unmount
  }, []);  // Runs only once when the component mounts

  return { validateAndRefreshToken };
};

export default useAuthToken;
