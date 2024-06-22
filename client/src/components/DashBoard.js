import React from 'react';
import { Link } from 'react-router-dom';
const Dashboard = () => {
    return (
        <div className="h-full w-64 bg-gray-800 text-white flex flex-col">
            <div className="p-5">Admin Dashboard</div>
            <ul className="flex flex-col p-5">
                <li>
                    <div className="py-2 px-4 hover:bg-gray-600 rounded">
                    <Link to="/bot" className="py-2 px-4  rounded">Discord Bot</Link>
                    </div>
                </li>
                <li>
                <div className="py-2 px-4 hover:bg-gray-600 rounded">
                    <Link to="/points-table" className="py-2 px-4  rounded">Points Table</Link>
                    </div>
                    <div className="py-2 px-4 hover:bg-gray-600 rounded">
                    <Link to="/points-table" className="py-2 px-4  rounded">Logger</Link>
                    </div>
        
                </li>
            </ul>
        </div>
    );
};


export default Dashboard;
