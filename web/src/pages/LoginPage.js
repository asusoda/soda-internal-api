import React, { useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import apiClient from '../components/utils/axios';  // Axios instance for making API requests

const LoginPage = () => {
    const navigate = useNavigate();

    // Function to handle login
    const handleLogin = () => {
        window.location.href = 'http://api.thesoda.io/auth/login';  // Redirect to your Flask backend login route
    };

    // Check if the token in localStorage is valid
    useEffect(() => {
        const validateToken = async () => {
            const token = localStorage.getItem('accessToken');

            if (token) {
                try {
                    const response = await apiClient.get('/auth/validateToken', {
                        headers: {
                            Authorization: token,  // Send the token in the Authorization header
                        },
                    });

                    if (response.data.valid && !response.data.expired) {
                        // If token is valid and not expired, redirect to /home
                        navigate('/home');
                    }
                } catch (error) {
                    console.log('Token validation failed:', error);
                    // If token is invalid or expired, stay on the login page
                }
            }
        };

        validateToken();
    }, [navigate]);

    return (
        <div className="min-h-screen flex items-center justify-center bg-gray-900 text-white">
            <div className="max-w-md w-full p-6 bg-gray-800 rounded-lg shadow-lg">
                <h1 className="text-3xl font-bold mb-6 text-center">SoDA at ASU</h1>
                <p className="mb-6 text-center">Log in with your Discord account to continue</p>
                <div className="flex justify-center">
                    <button
                        onClick={handleLogin}
                        className="w-full py-2 px-4 bg-blue-600 hover:bg-blue-700 rounded-md text-center text-white font-semibold transition-colors duration-300"
                    >
                        Login with Discord
                    </button>
                </div>
            </div>
        </div>
    );
};

export default LoginPage;
