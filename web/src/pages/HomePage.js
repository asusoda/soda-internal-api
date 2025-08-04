import React, { useState } from 'react';
import useAuthToken from '../hooks/userAuth';
import useOrgNavigation from '../hooks/useOrgNavigation';
import { useAuth } from '../components/auth/AuthContext';
import OrganizationNavbar from '../components/shared/OrganizationNavbar';
import { 
  FaUsers, 
  FaChartLine, 
  FaPlus, 
  FaClipboardList, 
  FaCogs, 
  FaGamepad,
  FaPlay,
  FaTrophy,
  FaSignOutAlt,
  FaTachometerAlt,
  FaCalendarAlt,
  FaUserPlus,
  FaFileUpload,
  FaRobot
} from 'react-icons/fa';

const HomePage = () => {
  useAuthToken();
  const { currentOrg } = useAuth();
  const { 
    goToUsers, 
    goToLeaderboard, 
    goToAddPoints,
    goToOCP,
    goToPanel,
    goToJeopardy,
    goToGamePanel,
    goToActiveGame
  } = useOrgNavigation();

  // Dashboard feature cards
  const dashboardFeatures = [
    {
      title: "User Management",
      description: "Manage users, view profiles, and handle user data",
      icon: FaUsers,
      color: "from-blue-500 to-blue-600",
      action: goToUsers
    },
    {
      title: "Leaderboard",
      description: "View points rankings and user statistics",
      icon: FaChartLine,
      color: "from-green-500 to-green-600",
      action: goToLeaderboard
    },
    {
      title: "Add Points",
      description: "Award points to users for events and activities",
      icon: FaPlus,
      color: "from-purple-500 to-purple-600",
      action: goToAddPoints
    },
    {
      title: "OCP System",
      description: "Officer Contribution Points tracking and management",
      icon: FaClipboardList,
      color: "from-indigo-500 to-indigo-600",
      action: goToOCP
    },
    {
      title: "Bot Control Panel",
      description: "Manage Discord bot settings and configurations",
      icon: FaRobot,
      color: "from-red-500 to-red-600",
      action: goToPanel
    },
    {
      title: "Jeopardy Game",
      description: "Host and manage Jeopardy game sessions",
      icon: FaTrophy,
      color: "from-yellow-500 to-yellow-600",
      action: goToJeopardy
    },
    {
      title: "Game Panel",
      description: "Manage game settings and configurations",
      icon: FaGamepad,
      color: "from-pink-500 to-pink-600",
      action: goToGamePanel
    },
    {
      title: "Active Game",
      description: "View and control currently running games",
      icon: FaPlay,
      color: "from-teal-500 to-teal-600",
      action: goToActiveGame
    }
  ];

  return (
    <OrganizationNavbar>
      <div className="max-w-7xl mx-auto">
        {/* Welcome Section */}
        <div className="text-center mb-12">
          <p className="text-xl text-gray-400 max-w-2xl mx-auto">
            Your central hub for managing users, tracking points, running games, and organizing events.
          </p>
        </div>

        {/* Feature Cards Grid */}
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-6">
          {dashboardFeatures.map((feature, index) => {
            const IconComponent = feature.icon;
            return (
              <div
                key={index}
                onClick={feature.action}
                className="group relative overflow-hidden rounded-xl bg-gray-900/50 backdrop-blur-sm border border-gray-700 hover:border-gray-500 transition-all duration-300 cursor-pointer transform hover:scale-105"
              >
                {/* Gradient Background */}
                <div className={`absolute inset-0 bg-gradient-to-br ${feature.color} opacity-0 group-hover:opacity-10 transition-opacity duration-300`} />
                
                {/* Card Content */}
                <div className="relative p-6">
                  <div className="flex items-center mb-4">
                    <div className={`p-3 rounded-lg bg-gradient-to-br ${feature.color} text-white`}>
                      <IconComponent className="w-6 h-6" />
                    </div>
                  </div>
                  
                  <h3 className="text-lg font-semibold mb-2 group-hover:text-white transition-colors">
                    {feature.title}
                  </h3>
                  
                  <p className="text-sm text-gray-400 group-hover:text-gray-300 transition-colors">
                    {feature.description}
                  </p>
                  
                  {/* Arrow indicator */}
                  <div className="absolute top-4 right-4 opacity-0 group-hover:opacity-100 transition-opacity duration-300">
                    <svg className="w-5 h-5 text-gray-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5l7 7-7 7" />
                    </svg>
                  </div>
                </div>
              </div>
            );
          })}
        </div>

        {/* Quick Stats Section */}
        <div className="mt-16 grid grid-cols-1 md:grid-cols-3 gap-6">
          <div className="bg-gray-900/50 backdrop-blur-sm rounded-lg border border-gray-700 p-6 text-center">
            <div className="flex items-center justify-center mb-2">
              <FaUsers className="w-8 h-8 text-blue-400" />
            </div>
            <h3 className="text-lg font-semibold mb-2">Active Users</h3>
            <p className="text-gray-400">Manage your community</p>
          </div>
          
          <div className="bg-gray-900/50 backdrop-blur-sm rounded-lg border border-gray-700 p-6 text-center">
            <div className="flex items-center justify-center mb-2">
              <FaTrophy className="w-8 h-8 text-yellow-400" />
            </div>
            <h3 className="text-lg font-semibold mb-2">Points System</h3>
            <p className="text-gray-400">Track achievements</p>
          </div>
          
          <div className="bg-gray-900/50 backdrop-blur-sm rounded-lg border border-gray-700 p-6 text-center">
            <div className="flex items-center justify-center mb-2">
              <FaGamepad className="w-8 h-8 text-purple-400" />
            </div>
            <h3 className="text-lg font-semibold mb-2">Interactive Games</h3>
            <p className="text-gray-400">Engage your members</p>
          </div>
        </div>
      </div>
    </OrganizationNavbar>
  );
};

export default HomePage;
