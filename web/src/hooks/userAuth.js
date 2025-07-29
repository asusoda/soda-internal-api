import { useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import apiClient from '../components/utils/axios';  // Update the path as necessary

const useAuthToken = () => {
  const navigate = useNavigate();

  // Function to validate and refresh the token
  const validateAndRefreshToken = async () => {
    const token = localStorage.getItem('accessToken');
    if (!token) {
      navigate('/');  // Redirect to login page if no token
      return;
    }

    try {
      const response = await apiClient.get('/auth/validateToken', {
        headers: {
          Authorization: token,
        },
      });

      if (response.data.valid && response.data.expired) {
        // Token expired, attempt to refresh it
        const refreshResponse = await apiClient.get('/auth/refresh', {
          headers: {
            Authorization: token,
          },
        });

        if (refreshResponse.data.valid && refreshResponse.data.token) {
          // Save the new token and continue
          const newToken = `Bearer ${refreshResponse.data.token}`;
          localStorage.setItem('accessToken', newToken);
        } else {
          navigate('/');  // Redirect if token refresh fails
        }
      } else if (!response.data.valid) {
        navigate('/');  // Redirect if token is invalid
      }
    } catch (error) {
      navigate('/');  // Redirect on error
    }
  };

  useEffect(() => {
    validateAndRefreshToken();  // Initial token validation

    const intervalId = setInterval(validateAndRefreshToken, 900000);  // 15 minutes

    return () => clearInterval(intervalId);  // Clear interval on unmount
  }, []);  // Runs only once when the component mounts
};

export default useAuthToken;
