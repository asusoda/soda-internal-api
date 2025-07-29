import React, { useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import apiClient from '../components/utils/axios';  // Axios instance for making API requests
import Orb from '../components/ui/Orb'; // Import the Orb component
import StarBorder from '../components/ui/StarBorder'; // Import the StarBorder component
import Logo from '../assets/logo-dark.svg'; // Updated import path for the logo
import { FaDiscord } from 'react-icons/fa'; // Import Discord icon

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
        <div className="relative min-h-screen flex flex-col items-center justify-center bg-soda-black text-soda-white overflow-hidden">
            {/* Sticky Logo */}
            <div className="absolute top-0 left-0 p-4 md:p-6 z-20">
                <img src={Logo} alt="SoDA Admin Logo" className="w-32 md:w-40" />
            </div>

            <div className="absolute inset-0 z-0">
                <Orb hue={300} forceHoverState={true} hoverIntensity={0.1} /> {/* Blue hue for the Orb */}
            </div>

            {/* Login Content */}
            <div className="relative z-10 max-w-md w-full p-8 bg-soda-black bg-opacity-80 rounded-lg shadow-2xl flex flex-col items-center mt-16 md:mt-0">
                <h1 className="text-3xl md:text-4xl font-bold mb-3 text-soda-white text-center">
                    SoDA Admin Panel
                </h1>
                <p className="mb-8 text-center text-gray-300 text-sm md:text-base">Admin dashboard for SoDA management. Please log in to continue.</p>
                <div className="flex justify-center w-full">
                    <StarBorder
                        onClick={handleLogin}
                        color="#FF3B30" // Red color for the star effect
                        speed="5s"
                        className="w-full max-w-xs"
                    >
                        <div className="flex items-center justify-center">
                            <FaDiscord className="mr-2 h-5 w-5" />
                            Login with Discord
                        </div>
                    </StarBorder>
                </div>
            </div>
        </div>
    );
};

export default LoginPage;
