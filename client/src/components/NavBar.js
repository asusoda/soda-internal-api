import React from 'react';
import LoginButton from './LoginButton';

const NavBar = () => {
    return (
        <nav className="bg-white/30 backdrop-blur-lg fixed top-0 left-0 right-0 z-50">
            <div className="max-w-6xl mx-auto px-4">
                <div className="flex justify-between items-center py-3">
                    <div className="text-lg font-semibold">
                        {/* Replace with your logo or brand name */}
                        <a href="/" className="text-gray-800 hover:text-gray-600 transition">Brand</a>
                    </div>
                    <LoginButton />
                </div>
            </div>
        </nav>
    );
};

export default NavBar;