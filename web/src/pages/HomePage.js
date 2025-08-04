import React, { useState } from 'react';
import useAuthToken from '../hooks/userAuth';
import useOrgNavigation from '../hooks/useOrgNavigation';
import { useAuth } from '../components/auth/AuthContext';
import { Menu, MenuItem, HoveredLink } from '../components/ui/navbar-menu';
import OrganizationSwitcher from '../components/OrganizationSwitcher';
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
import Orb from '../components/ui/Orb';
import { FileUpload } from '../components/ui/file-upload';
import StarBorder from '../components/ui/StarBorder';
const HomePage = () => {
  useAuthToken();
  const { logout, currentOrg } = useAuth();
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

  const [activeNavItem, setActiveNavItem] = useState(null);

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
    <div className="relative min-h-screen bg-black text-white overflow-hidden">
      {/* Background Effects */}
      <div className="absolute inset-0">
        <Orb />
      </div>
  
      {/* Navigation */}
      <div className="relative z-20 w-full">
        <Menu setActive={setActiveNavItem}>
          {/* Left side - Organization info */}
          <div className="flex items-center space-x-3 lg:space-x-4 flex-shrink-0">
            {currentOrg && (
              <div className="flex items-center space-x-2">
                {currentOrg.icon_url && (
                  <img 
                    src={currentOrg.icon_url} 
                    alt={currentOrg.name}
                    className="w-6 h-6 lg:w-8 lg:h-8 rounded-full flex-shrink-0"
                  />
                )}
                <div className="min-w-0">
                  <h1 className="text-sm lg:text-xl font-bold truncate max-w-48 lg:max-w-64">{currentOrg.name}</h1>
                  <p className="text-xs lg:text-sm text-gray-400 truncate">Dashboard • /{currentOrg.prefix}</p>
                </div>
              </div>
            )}
          </div>
  

            {/* Center - Quick Navigation */}
        <div className="flex items-center space-x-4 lg:space-x-6 flex-shrink-0">
          <MenuItem setActive={setActiveNavItem} active={activeNavItem} item="Quick Access">
            <div className="flex flex-col space-y-4 text-sm">
              <HoveredLink onClick={goToUsers}>
                <FaUsers className="inline mr-2" />User Management
              </HoveredLink>
              <HoveredLink onClick={goToLeaderboard}>
                <FaChartLine className="inline mr-2" />Leaderboard
              </HoveredLink>
              <HoveredLink onClick={goToAddPoints}>
                <FaPlus className="inline mr-2" />Add Points
              </HoveredLink>
              <HoveredLink onClick={goToOCP}>
                <FaClipboardList className="inline mr-2" />OCP Details
              </HoveredLink>
            </div>
          </MenuItem>

          <MenuItem setActive={setActiveNavItem} active={activeNavItem} item="Games">
            <div className="flex flex-col space-y-4 text-sm">
              <HoveredLink onClick={goToJeopardy}>
                <FaTrophy className="inline mr-2" />Jeopardy
              </HoveredLink>
              <HoveredLink onClick={goToGamePanel}>
                <FaGamepad className="inline mr-2" />Game Panel
              </HoveredLink>
              <HoveredLink onClick={goToActiveGame}>
                <FaPlay className="inline mr-2" />Active Game
              </HoveredLink>
              <HoveredLink onClick={goToPanel}>
                <FaRobot className="inline mr-2" />Bot Panel
              </HoveredLink>
            </div>
          </MenuItem>
        </div>

             {/* Right side - Organization switcher and logout */}
        <div className="flex items-center space-x-2 lg:space-x-4 flex-shrink-0">
          <OrganizationSwitcher />
          <button 
            onClick={logout}
            className="flex items-center space-x-1 lg:space-x-2 px-2 lg:px-3 py-2 rounded-md text-xs lg:text-sm font-medium text-gray-300 hover:text-white hover:bg-gray-700 transition-colors"
          >
            <FaSignOutAlt className="w-3 h-3 lg:w-4 lg:h-4" />
            <span className="hidden sm:inline">Logout</span>
          </button>
        </div>
      </Menu>
    </div>

    {/* Main Dashboard Content */}
    <div className="relative z-10 px-4 py-8">
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
              <h3 className="text-2xl font-bold mb-1">Active Users</h3>
              <p className="text-gray-400">Manage your community</p>
            </div>
            
            <div className="bg-gray-900/50 backdrop-blur-sm rounded-lg border border-gray-700 p-6 text-center">
              <div className="flex items-center justify-center mb-2">
                <FaTrophy className="w-8 h-8 text-yellow-400" />
              </div>
              <h3 className="text-2xl font-bold mb-1">Points System</h3>
              <p className="text-gray-400">Track achievements</p>
            </div>
            
            <div className="bg-gray-900/50 backdrop-blur-sm rounded-lg border border-gray-700 p-6 text-center">
              <div className="flex items-center justify-center mb-2">
                <FaGamepad className="w-8 h-8 text-purple-400" />
              </div>
              <h3 className="text-2xl font-bold mb-1">Interactive Games</h3>
              <p className="text-gray-400">Engage your members</p>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};

export default HomePage;
