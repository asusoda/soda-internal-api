import React, { useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { FaBars, FaTimes, FaSignOutAlt } from 'react-icons/fa';

const Dashboard = () => {
    const [isMobileMenuOpen, setIsMobileMenuOpen] = useState(false);
    const navigate = useNavigate();

    const handleLogout = () => {
        localStorage.removeItem('accessToken');
        localStorage.removeItem('refreshToken');
        navigate('/');
        setIsMobileMenuOpen(false);
    };

    return (
        <div className="h-full w-full md:w-64 bg-gray-800 text-white flex flex-col">
            <div className="p-5 flex justify-between items-center">
                <span>Admin Dashboard</span>
                <button
                    className="md:hidden text-white"
                    onClick={() => setIsMobileMenuOpen(!isMobileMenuOpen)}
                >
                    {isMobileMenuOpen ? <FaTimes size={24} /> : <FaBars size={24} />}
                </button>
            </div>
            <ul className="hidden md:flex flex-col p-5">
                <li>
                    <div className="py-2 px-4 hover:bg-gray-600 rounded">
                    <Link to="/bot" className="py-2 px-4 rounded">Discord Bot</Link>
                    </div>
                </li>
                <li>
                <div className="py-2 px-4 hover:bg-gray-600 rounded">
                    <Link to="/points-table" className="py-2 px-4 rounded">Points Table</Link>
                    </div>
                    <div className="py-2 px-4 hover:bg-gray-600 rounded">
                    <Link to="/points-table" className="py-2 px-4 rounded">Logger</Link>
                    </div>
                </li>
                <li>
                    <button
                        onClick={handleLogout}
                        className="w-full text-left py-2 px-4 hover:bg-gray-600 rounded flex items-center"
                    >
                        <FaSignOutAlt className="mr-2" /> Logout
                    </button>
                </li>
            </ul>
            {isMobileMenuOpen && (
                <div className="md:hidden absolute top-16 left-0 w-full bg-gray-800 z-20">
                    <ul className="flex flex-col p-5">
                        <li className="w-full">
                            <Link to="/bot" className="block py-3 px-4 hover:bg-gray-700 rounded" onClick={() => setIsMobileMenuOpen(false)}>Discord Bot</Link>
                        </li>
                        <li className="w-full">
                            <Link to="/points-table" className="block py-3 px-4 hover:bg-gray-700 rounded" onClick={() => setIsMobileMenuOpen(false)}>Points Table</Link>
                        </li>
                        <li className="w-full">
                            <Link to="/points-table" className="block py-3 px-4 hover:bg-gray-700 rounded" onClick={() => setIsMobileMenuOpen(false)}>Logger</Link>
                        </li>
                        <li className="w-full">
                            <button
                                onClick={handleLogout} 
                                className="w-full text-left block py-3 px-4 hover:bg-gray-700 rounded flex items-center"
                            >
                                <FaSignOutAlt className="mr-2" /> Logout
                            </button>
                        </li>
                    </ul>
                </div>
            )}
        </div>
    );
};

export default Dashboard;
