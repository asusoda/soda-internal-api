import React, { useState } from "react";
import useAuthToken from "../hooks/userAuth";
import useOrgNavigation from "../hooks/useOrgNavigation";
import useOrgModules from "../hooks/useOrgModules";
import { useAuth } from "../components/auth/AuthContext";
import OrganizationNavbar from "../components/shared/OrganizationNavbar";
import {
  FaUsers,
  FaChartLine,
  FaPlus,
  FaCogs,
  FaSignOutAlt,
  FaTachometerAlt,
  FaCalendarAlt,
  FaStore,
  FaChevronDown,
  FaChevronUp,
  FaServer,
} from "react-icons/fa";

const HomePage = () => {
  useAuthToken();
  const { currentOrg } = useAuth();
  const {
    goToUsers,
    goToLeaderboard,
    goToAddPoints,
    goToAddProducts,
    goToOrders,
  } = useOrgNavigation();
  const { isEnabled } = useOrgModules();

  // State for managing dropdown visibility
  const [expandedCategories, setExpandedCategories] = useState({
    userManagement: true,
    storeFront: true,
    calendar: true,
    compute: true,
    discordBots: true,
  });

  // Toggle dropdown visibility
  const toggleCategory = (category) => {
    setExpandedCategories(prev => ({
      ...prev,
      [category]: !prev[category]
    }));
  };

  // Dashboard categories with their features
  const allCategories = [
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
          module: "points",
          description: "View points rankings and user statistics",
          icon: FaChartLine,
          color: "from-green-500 to-green-600",
          action: goToLeaderboard,
        },
        {
          title: "Add Points",
          module: "points",
          description: "Award points to users for events and activities",
          icon: FaPlus,
          color: "from-purple-500 to-purple-600",
          action: goToAddPoints,
        },
      ],
    },
    {
      id: "storeFront",
      module: "storefront",
      title: "Store Front",
      icon: FaStore,
      color: "from-orange-500 to-orange-600",
      description: "Manage storefront and store operations",
      features: [
        {
          title: "Admin Dashboard",
          description: "Comprehensive storefront management dashboard",
          icon: FaTachometerAlt,
          color: "from-orange-500 to-orange-600",
          action: () => window.location.href = `/${currentOrg?.prefix}/storefront/dashboard`,
        },
        {
          title: "Store & Orders",
          description: "Browse products, shop, and track orders",
          icon: FaStore,
          color: "from-blue-500 to-blue-600",
          action: () => window.open(`/store/${currentOrg?.prefix}`, '_blank'),
        },
        {
          title: "Add Products",
          description: "Add new products to storefront (Admin)",
          icon: FaPlus,
          color: "from-pink-500 to-pink-600",
          action: goToAddProducts,
        },
        {
          title: "Manage Orders",
          description: "View and manage all orders (Admin)",
          icon: FaSignOutAlt,
          color: "from-gray-500 to-gray-600",
          action: goToOrders,
        },
      ],
    },
    {
      id: "calendar",
      module: "calendar",
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
      id: "compute",
      module: "godfather",
      title: "Godfather",
      icon: FaServer,
      color: "from-cyan-500 to-cyan-600",
      description: "GPU and CPU pods members SSH into",
      features: [
        {
          title: "Pods",
          description: "Create pods, choose who may connect, manage files",
          icon: FaServer,
          color: "from-cyan-500 to-cyan-600",
          action: () => (window.location.href = `/${currentOrg?.prefix}/compute`),
        },
      ],
    },
  ];

  // Switched-off modules are hidden; their routes return 404 for this org.
  const dashboardCategories = allCategories
    .filter((category) => isEnabled(category.module))
    .map((category) => ({
      ...category,
      features: category.features.filter((feature) => isEnabled(feature.module)),
    }));

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
        <div className="mt-16 grid grid-cols-1 md:grid-cols-3 gap-6">
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
            <p className="text-gray-400 text-sm">Manage storefront</p>
          </div>

          <div className="bg-gray-900/50 backdrop-blur-sm rounded-lg border border-gray-700 p-6 text-center">
            <div className="flex items-center justify-center mb-2">
              <FaCalendarAlt className="w-8 h-8 text-red-400" />
            </div>
            <h3 className="text-lg font-semibold mb-2 text-white">Calendar</h3>
            <p className="text-gray-400 text-sm">Manage events</p>
          </div>
        </div>
      </div>
    </OrganizationNavbar>
  );
};

export default HomePage;
