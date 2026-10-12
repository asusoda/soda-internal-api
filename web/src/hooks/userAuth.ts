import { useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { useAuth } from '../components/auth/AuthContext';
import useLatestRef from './useLatestRef';

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

  // Call the latest validateAndRefreshToken, so the interval uses the current token.
  const validateRef = useLatestRef(validateAndRefreshToken);

  useEffect(() => {
    const validate = () => validateRef.current();
    validate();  // Initial token validation

    const intervalId = setInterval(validate, 900000);  // 15 minutes

    return () => clearInterval(intervalId);  // Clear interval on unmount
  }, [validateRef]);  // Runs only once when the component mounts

  return { validateAndRefreshToken };
};

export default useAuthToken;
