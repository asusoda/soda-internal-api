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
  FaRobot
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
              className="cursor-pointer flex items-center space-x-1 lg:space-x-2 px-2 lg:px-3 py-2 rounded-md text-xs lg:text-sm font-medium text-gray-300 hover:text-white hover:bg-gray-700 transition-colors duration-200"
            >
              <FaSignOutAlt className="w-3 h-3 lg:w-4 lg:h-4" />
              <span className="hidden sm:inline">Logout</span>
            </button>
          </div>
        </Menu>
      </div>

      {/* Main Content */}
      <div className="relative z-10 px-4 py-8">
        {children}
      </div>
    </div>
  );
};

export default OrganizationNavbar; 