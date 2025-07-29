import React from 'react';
import { FaUser, FaChartLine, FaDiscord, FaHome, FaPlus } from 'react-icons/fa'; 
import { useNavigate } from 'react-router-dom';
import './SideBar.css'; 

const Sidebar = ({ isSidebarOpen, toggleSidebar }) => {
    const navigate = useNavigate();

    return (
        <div className={`sidebar ${isSidebarOpen ? 'open' : ''}`} style={{ backgroundColor: '#ba3554' }}>
            <button className="close-btn" onClick={toggleSidebar}>
                {isSidebarOpen ? '✖' : '☰'}
            </button>
            <div className={`sidebar-links ${isSidebarOpen ? 'visible' : 'hidden'}`}>
                <button onClick={() => navigate('/home')}>
                    <FaHome className="icon" />
                    {isSidebarOpen && <span>Home</span>}
                </button>
                <button onClick={() => navigate('/users')}>
                    <FaUser className="icon" />
                    {isSidebarOpen && <span>Users</span>}
                </button>
                <button onClick={() => navigate('/leaderboard')}>
                    <FaChartLine className="icon" />
                    {isSidebarOpen && <span>Points</span>}
                </button>
                <button onClick={() => navigate('/createuser')}>
                    <FaPlus className="icon" />
                    {isSidebarOpen && <span>Create User</span>}
                </button>
                {/* Uncomment this if needed
                <button onClick={() => navigate('/discord')}>
                    <FaDiscord className="icon" />
                    {isSidebarOpen && <span>Discord</span>}
                </button>
                */}
            </div>
        </div>
    );
};

export default Sidebar;
