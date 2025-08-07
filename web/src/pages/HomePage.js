import React, { useState } from "react";
import useAuthToken from "../hooks/userAuth";
import useOrgNavigation from "../hooks/useOrgNavigation";
import { useAuth } from "../components/auth/AuthContext";
import OrganizationNavbar from "../components/shared/OrganizationNavbar";
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
  FaRobot,
  FaStore,
  FaChevronDown,
  FaChevronUp,
} from "react-icons/fa";

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
    goToActiveGame,
    goToMerchProducts,
    goToAddProducts,
    goToOrders,
  } = useOrgNavigation();

  // State for managing dropdown visibility
  const [expandedCategories, setExpandedCategories] = useState({
    userManagement: true,
    storeFront: true,
    ocp: true,
    discordBots: true,
    calendar: true,
  });

  // Toggle dropdown visibility
  const toggleCategory = (category) => {
    setExpandedCategories(prev => ({
      ...prev,
      [category]: !prev[category]
    }));
  };

  // Dashboard categories with their features
  const dashboardCategories = [
    {
      id: "userManagement",
      title: "User Management",
      icon: FaUsers,
      color: "from-blue-500 to-blue-600",
      description: "Manage users, points, and community engagement",
      features: [
        {
          title: "User Management",
          description: "Manage users, view profiles, and handle user data",
          icon: FaUsers,
          color: "from-blue-500 to-blue-600",
          action: goToUsers,
        },
        {
          title: "Leaderboard",
          description: "View points rankings and user statistics",
          icon: FaChartLine,
          color: "from-green-500 to-green-600",
          action: goToLeaderboard,
        },
        {
          title: "Add Points",
          description: "Award points to users for events and activities",
          icon: FaPlus,
          color: "from-purple-500 to-purple-600",
          action: goToAddPoints,
        },
      ],
    },
    {
      id: "storeFront",
      title: "Store Front",
      icon: FaStore,
      color: "from-orange-500 to-orange-600",
      description: "Manage merchandise and store operations",
      features: [
        {
          title: "Merchandise",
          description: "Manage merchandise and product listings",
          icon: FaFileUpload,
          color: "from-orange-500 to-orange-600",
          action: goToMerchProducts,
        },
        {
          title: "Add Products",
          description: "Add new merchandise products",
          icon: FaPlus,
          color: "from-pink-500 to-pink-600",
          action: goToAddProducts,
        },
        {
          title: "Orders",
          description: "View and manage merchandise orders",
          icon: FaSignOutAlt,
          color: "from-gray-500 to-gray-600",
          action: goToOrders,
        },
      ],
    },
    {
      id: "ocp",
      title: "OCP System",
      icon: FaClipboardList,
      color: "from-indigo-500 to-indigo-600",
      description: "Officer Contribution Points tracking and management",
      features: [
        {
          title: "OCP Details",
          description: "Officer Contribution Points tracking and management",
          icon: FaClipboardList,
          color: "from-indigo-500 to-indigo-600",
          action: goToOCP,
        },
      ],
    },
    {
      id: "calendar",
      title: "Calendar System",
      icon: FaCalendarAlt,
      color: "from-red-500 to-red-600",
      description: "Manage events and calendar synchronization",
      features: [
        {
          title: "Calendar View",
          description: "View and manage organization events",
          icon: FaCalendarAlt,
          color: "from-red-500 to-red-600",
          action: () => window.location.href = `/${currentOrg?.prefix}/calendar`,
        },
        {
          title: "Sync Settings",
          description: "Configure Notion and Google Calendar sync",
          icon: FaCogs,
          color: "from-yellow-500 to-yellow-600",
          action: () => window.location.href = `/${currentOrg?.prefix}/calendar/settings`,
        },
      ],
    },
    {
      id: "discordBots",
      title: "Discord Bots",
      icon: FaRobot,
      color: "from-purple-500 to-purple-600",
      description: "Manage Discord bot settings and game systems",
      features: [
        {
          title: "Bot Control Panel",
          description: "Manage Discord bot settings and configurations",
          icon: FaRobot,
          color: "from-purple-500 to-purple-600",
          action: goToPanel,
        },
        {
          title: "Jeopardy Game",
          description: "Host and manage Jeopardy game sessions",
          icon: FaTrophy,
          color: "from-yellow-500 to-yellow-600",
          action: goToJeopardy,
        },
        {
          title: "Game Panel",
          description: "Manage game settings and configurations",
          icon: FaGamepad,
          color: "from-pink-500 to-pink-600",
          action: goToGamePanel,
        },
        {
          title: "Active Game",
          description: "View and control currently running games",
          icon: FaPlay,
          color: "from-teal-500 to-teal-600",
          action: goToActiveGame,
        },
      ],
    },
  ];

  return (
    <OrganizationNavbar>
      <div className="max-w-7xl mx-auto">
        {/* Welcome Section */}
        <div className="text-center mb-12">
          <h1 className="text-4xl font-bold mb-4 text-white">
            Hey there <span className="text-blue-500">{currentOrg?.name || "Your Organization"} </span> !!
          </h1>
          <p className="text-xl text-gray-400 max-w-3xl mx-auto">
            Welcome to SoDA's Internal Toolset. Here you can manage your organization. 
          </p>
        </div>

        {/* Categories Grid */}
        <div className="space-y-10">
          {dashboardCategories.map((category) => {
            const CategoryIcon = category.icon;
            const isExpanded = expandedCategories[category.id];
            
            return (
              <div
                key={category.id}
                className="border border-gray-700/50 backdrop-blur-lg rounded-xl overflow-hidden"
              >
                {/* Category Header */}
                <div
                  className="p-6 cursor-pointer transition-colors"
                  onClick={() => toggleCategory(category.id)}
                >
                  <div className="flex items-center justify-between">
                    <div className="flex items-center space-x-4">
                      <div
                        className={`p-3 rounded-lg text-white`}
                      >
                        <CategoryIcon className="w-6 h-6" />
                      </div>
                      <div>
                        <h2 className="text-xl font-semibold text-white">
                          {category.title}
                        </h2>
                        <p className="text-gray-400 text-sm">
                          {category.description}
                        </p>
                      </div>
                    </div>
                    <div className="flex items-center space-x-2">
                      <span className="text-sm text-gray-400">
                        {category.features.length} features
                      </span>
                      {isExpanded ? (
                        <FaChevronUp className="w-5 h-5 text-gray-400" />
                      ) : (
                        <FaChevronDown className="w-5 h-5 text-gray-400" />
                      )}
                    </div>
                  </div>
                </div>

                {/* Category Content */}
                {isExpanded && (
                  <div className="p-6">
                    <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
                      {category.features.map((feature, index) => {
                        const FeatureIcon = feature.icon;
                        return (
                          <div
                            key={index}
                            onClick={feature.action}
                            className="group relative overflow-hidden rounded-lg bg-black/50 border border-gray-700/50 hover:border-gray-500 transition-all duration-300 cursor-pointer transform hover:scale-105"
                          >
                            {/* Gradient Background */}
                            <div
                              className={`absolute inset-0 bg-gradient-to-br ${feature.color} opacity-0 group-hover:opacity-10 transition-opacity duration-300`}
                            />

                            {/* Card Content */}
                            <div className="relative p-4">
                              <div className="flex items-center mb-3">
                                <div
                                  className={`p-2 rounded-lg bg-gradient-to-br ${feature.color} text-white`}
                                >
                                  <FeatureIcon className="w-5 h-5" />
                                </div>
                              </div>

                              <h3 className="text-base font-semibold mb-2 group-hover:text-white transition-colors">
                                {feature.title}
                              </h3>

                              <p className="text-xs text-gray-400 group-hover:text-gray-300 transition-colors">
                                {feature.description}
                              </p>

                              {/* Arrow indicator */}
                              <div className="absolute top-3 right-3 opacity-0 group-hover:opacity-100 transition-opacity duration-300">
                                <svg
                                  className="w-4 h-4 text-gray-400"
                                  fill="none"
                                  stroke="currentColor"
                                  viewBox="0 0 24 24"
                                >
                                  <path
                                    strokeLinecap="round"
                                    strokeLinejoin="round"
                                    strokeWidth={2}
                                    d="M9 5l7 7-7 7"
                                  />
                                </svg>
                              </div>
                            </div>
                          </div>
                        );
                      })}
                    </div>
                  </div>
                )}
              </div>
            );
          })}
        </div>

        {/* Quick Stats Section */}
        <div className="mt-16 grid grid-cols-1 md:grid-cols-5 gap-6">
          <div className="bg-gray-900/50 backdrop-blur-sm rounded-lg border border-gray-700 p-6 text-center">
            <div className="flex items-center justify-center mb-2">
              <FaUsers className="w-8 h-8 text-blue-400" />
            </div>
            <h3 className="text-lg font-semibold mb-2 text-white">User Management</h3>
            <p className="text-gray-400 text-sm">Manage your community</p>
          </div>

          <div className="bg-gray-900/50 backdrop-blur-sm rounded-lg border border-gray-700 p-6 text-center">
            <div className="flex items-center justify-center mb-2">
              <FaStore className="w-8 h-8 text-orange-400" />
            </div>
            <h3 className="text-lg font-semibold mb-2 text-white">Store Front</h3>
            <p className="text-gray-400 text-sm">Manage merchandise</p>
          </div>

          <div className="bg-gray-900/50 backdrop-blur-sm rounded-lg border border-gray-700 p-6 text-center">
            <div className="flex items-center justify-center mb-2">
              <FaClipboardList className="w-8 h-8 text-indigo-400" />
            </div>
            <h3 className="text-lg font-semibold mb-2 text-white">OCP System</h3>
            <p className="text-gray-400 text-sm">Track officer contributions</p>
          </div>

          <div className="bg-gray-900/50 backdrop-blur-sm rounded-lg border border-gray-700 p-6 text-center">
            <div className="flex items-center justify-center mb-2">
              <FaCalendarAlt className="w-8 h-8 text-red-400" />
            </div>
            <h3 className="text-lg font-semibold mb-2 text-white">Calendar</h3>
            <p className="text-gray-400 text-sm">Manage events</p>
          </div>

          <div className="bg-gray-900/50 backdrop-blur-sm rounded-lg border border-gray-700 p-6 text-center">
            <div className="flex items-center justify-center mb-2">
              <FaRobot className="w-8 h-8 text-purple-400" />
            </div>
            <h3 className="text-lg font-semibold mb-2 text-white">Discord Bots</h3>
            <p className="text-gray-400 text-sm">Manage bot systems</p>
          </div>
        </div>
      </div>
    </OrganizationNavbar>
  );
};

export default HomePage;
