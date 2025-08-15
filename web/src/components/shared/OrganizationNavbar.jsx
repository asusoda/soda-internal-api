import React, { useState } from 'react';
import { useAuth } from '../auth/AuthContext';
import { useNavigate } from 'react-router-dom';
import { Menu, MenuItem, HoveredLink } from '../ui/navbar-menu';
import OrganizationSwitcher from '../OrganizationSwitcher';
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
  FaRobot,
  FaStore,
  FaCalendarAlt,
  FaDiscord
} from 'react-icons/fa';
import Orb from '../ui/Orb';

const OrganizationNavbar = ({ children }) => {
  const { logout, currentOrg, isSuperAdmin } = useAuth();
  const navigate = useNavigate();
  const [activeNavItem, setActiveNavItem] = useState(null);

  const goToDashboard = () => navigate(`/${currentOrg?.prefix}/dashboard`);
  const goToUsers = () => navigate(`/${currentOrg?.prefix}/users`);
  const goToLeaderboard = () => navigate(`/${currentOrg?.prefix}/leaderboard`);
  const goToAddPoints = () => navigate(`/${currentOrg?.prefix}/addpoints`);
  const goToOCP = () => navigate(`/${currentOrg?.prefix}/ocp`);
  const goToPanel = () => navigate(`/${currentOrg?.prefix}/panel`);
  const goToJeopardy = () => navigate(`/${currentOrg?.prefix}/jeopardy`);
  const goToGamePanel = () => navigate(`/${currentOrg?.prefix}/gamepanel`);
  const goToActiveGame = () => navigate(`/${currentOrg?.prefix}/activegame`);
  const goToStorefront = () => navigate(`/${currentOrg?.prefix}/storefront`);
  const goToCalendar = () => navigate(`/${currentOrg?.prefix}/calendar`);
  const goToDiscordBots = () => navigate(`/${currentOrg?.prefix}/discord-bots`);

  return (
    <div className="relative min-h-screen bg-black text-white overflow-hidden">
      {/* Background Effects */}
      <div className="absolute inset-0">
        <Orb hue={300} forceHoverState={true} hoverIntensity={0.1} />
      </div>

      {/* Navigation */}
      <div className="relative z-20 w-full">
        <Menu setActive={setActiveNavItem}>
          {/* Left side - Org logo and name */}
          <div className="flex items-center space-x-2 lg:space-x-4 flex-shrink-0">
            {currentOrg && (
              <div className="flex items-center space-x-2">
                {currentOrg.icon_url && (
                  <img 
                    src={currentOrg.icon_url} 
                    alt={currentOrg.name}
                    className="w-6 h-6 lg:w-8 lg:h-8 rounded-full flex-shrink-0"
                  />
                )}
                <h1 className="text-sm lg:text-xl font-bold truncate max-w-2xl lg:max-w-3xl">{currentOrg.name}</h1>
              </div>
            )}
          </div>

          {/* Center - Navigation Items */}
          <div className="flex items-center space-x-4 lg:space-x-6 flex-shrink-0">
            <MenuItem setActive={setActiveNavItem} active={activeNavItem} item="Dashboard">
              <HoveredLink onClick={goToDashboard}>
                <FaTachometerAlt className="inline mr-2" />Dashboard
              </HoveredLink>
            </MenuItem>
            <MenuItem setActive={setActiveNavItem} active={activeNavItem} item="Quick Access">
              <h3 className="text-xl font-bold text-white mb-8 text-center">Quick Access</h3>
              <div className="grid grid-cols-5 gap-8">
                {/* User Management Category */}
                <div>
                  <div className="text-sm font-semibold text-blue-400 mb-4 flex items-center">
                    <FaUsers className="mr-2 text-blue-400" />
                    User Management
                  </div>
                  <ul className="space-y-2">
                    <li>
                      <HoveredLink onClick={goToUsers} className="block p-2 rounded hover:bg-blue-400/20 hover:text-blue-300 transition-all duration-200 text-sm text-gray-300">
                        • Manage Users
                      </HoveredLink>
                    </li>
                    <li>
                      <HoveredLink onClick={goToLeaderboard} className="block p-2 rounded hover:bg-blue-400/20 hover:text-blue-300 transition-all duration-200 text-sm text-gray-300">
                        • Leaderboard
                      </HoveredLink>
                    </li>
                    <li>
                      <HoveredLink onClick={goToAddPoints} className="block p-2 rounded hover:bg-blue-400/20 hover:text-blue-300 transition-all duration-200 text-sm text-gray-300">
                        • Add Points
                      </HoveredLink>
                    </li>
                  </ul>
                </div>

                {/* Store Front Category */}
                <div>
                  <div className="text-sm font-semibold text-green-400 mb-4 flex items-center">
                    <FaStore className="mr-2 text-green-400" />
                    Store Front
                  </div>
                  <ul className="space-y-2">
                    <li>
                      <HoveredLink onClick={goToStorefront} className="block p-2 rounded hover:bg-green-400/20 hover:text-green-300 transition-all duration-200 text-sm text-gray-300">
                        • Merchandise
                      </HoveredLink>
                    </li>
                    <li>
                      <HoveredLink onClick={goToStorefront} className="block p-2 rounded hover:bg-green-400/20 hover:text-green-300 transition-all duration-200 text-sm text-gray-300">
                        • Add Products
                      </HoveredLink>
                    </li>
                    <li>
                      <HoveredLink onClick={goToStorefront} className="block p-2 rounded hover:bg-green-400/20 hover:text-green-300 transition-all duration-200 text-sm text-gray-300">
                        • Orders
                      </HoveredLink>
                    </li>
                  </ul>
                </div>

                {/* OCP System Category */}
                <div>
                  <div className="text-sm font-semibold text-purple-400 mb-4 flex items-center">
                    <FaClipboardList className="mr-2 text-purple-400" />
                    OCP System
                  </div>
                  <ul className="space-y-2">
                    <li>
                      <HoveredLink onClick={goToOCP} className="block p-2 rounded hover:bg-purple-400/20 hover:text-purple-300 transition-all duration-200 text-sm text-gray-300">
                        • OCP Details
                      </HoveredLink>
                    </li>
                  </ul>
                </div>

                {/* Calendar System Category */}
                <div>
                  <div className="text-sm font-semibold text-yellow-400 mb-4 flex items-center">
                    <FaCalendarAlt className="mr-2 text-yellow-400" />
                    Calendar System
                  </div>
                  <ul className="space-y-2">
                    <li>
                      <HoveredLink onClick={goToCalendar} className="block p-2 rounded hover:bg-yellow-400/20 hover:text-yellow-300 transition-all duration-200 text-sm text-gray-300">
                        • Calendar View
                      </HoveredLink>
                    </li>
                    <li>
                      <HoveredLink onClick={goToCalendar} className="block p-2 rounded hover:bg-yellow-400/20 hover:text-yellow-300 transition-all duration-200 text-sm text-gray-300">
                        • Sync Settings
                      </HoveredLink>
                    </li>
                  </ul>
                </div>

                {/* Discord Bots Category */}
                <div>
                  <div className="text-sm font-semibold text-indigo-400 mb-4 flex items-center">
                    <FaDiscord className="mr-2 text-indigo-400" />
                    Discord Bots
                  </div>
                  <ul className="space-y-2">
                    <li>
                      <HoveredLink onClick={goToPanel} className="block p-2 rounded hover:bg-indigo-400/20 hover:text-indigo-300 transition-all duration-200 text-sm text-gray-300">
                        • Bot Control Panel
                      </HoveredLink>
                    </li>
                    <li>
                      <HoveredLink onClick={goToJeopardy} className="block p-2 rounded hover:bg-indigo-400/20 hover:text-indigo-300 transition-all duration-200 text-sm text-gray-300">
                        • Jeopardy Game
                      </HoveredLink>
                    </li>
                    <li>
                      <HoveredLink onClick={goToGamePanel} className="block p-2 rounded hover:bg-indigo-400/20 hover:text-indigo-300 transition-all duration-200 text-sm text-gray-300">
                        • Game Panel
                      </HoveredLink>
                    </li>
                    <li>
                      <HoveredLink onClick={goToActiveGame} className="block p-2 rounded hover:bg-indigo-400/20 hover:text-indigo-300 transition-all duration-200 text-sm text-gray-300">
                        • Active Game
                      </HoveredLink>
                    </li>
                  </ul>
                </div>
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
              className="cursor-pointer flex items-center space-x-1 lg:space-x-2 px-2 lg:px-3 py-2 rounded-md text-xs lg:text-sm font-medium text-gray-300 hover:text-white hover:bg-gray-700 transition-colors duration-200"
            >
              <FaSignOutAlt className="w-3 h-3 lg:w-4 lg:h-4" />
              <span className="hidden sm:inline">Logout</span>
            </button>
          </div>
        </Menu>
      </div>

      {/* Main Content */}
      <div className="relative z-10 px-4 py-10 mt-20">
        {children}
      </div>
    </div>
  );
};

export default OrganizationNavbar; 