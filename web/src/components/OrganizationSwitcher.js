import React, { useState, useEffect, useRef } from 'react';
import { useAuth } from './auth/AuthContext';
import { useNavigate } from 'react-router-dom';

const OrganizationSwitcher = ({ className = '' }) => {
  const { currentOrg, organizations, selectOrganization, isSuperAdmin } = useAuth();
  const [isOpen, setIsOpen] = useState(false);
  const navigate = useNavigate();
  const dropdownRef = useRef(null);

  const handleOrgSwitch = (org) => {
    selectOrganization(org);
    setIsOpen(false);
  };

  const handleViewAllOrgs = () => {
    navigate('/select-organization');
    setIsOpen(false);
  };

  const handleSuperAdmin = () => {
    navigate('/superadmin');
    setIsOpen(false);
  };

  // Close dropdown when clicking outside
  useEffect(() => {
    const handleClickOutside = (event) => {
      if (dropdownRef.current && !dropdownRef.current.contains(event.target)) {
        setIsOpen(false);
      }
    };

    if (isOpen) {
      document.addEventListener('mousedown', handleClickOutside);
      return () => {
        document.removeEventListener('mousedown', handleClickOutside);
      };
    }
  }, [isOpen]);

  // Don't render if no org selected or only one org (unless superadmin)
  if (!currentOrg || (organizations.length <= 1 && !isSuperAdmin)) {
    return null;
  }

  return (
    <div className={`relative ${className}`} ref={dropdownRef}>
      <button
        onClick={() => setIsOpen(!isOpen)}
        className="flex items-center space-x-2 px-3 py-2 rounded-md text-sm font-medium text-gray-300 hover:text-white hover:bg-gray-700 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-offset-gray-800 focus:ring-white transition-all duration-200"
      >
        {currentOrg.icon_url && (
          <img
            src={currentOrg.icon_url}
            alt={`${currentOrg.name} icon`}
            className="w-6 h-6 rounded-full"
          />
        )}
        <span className="truncate max-w-32">{currentOrg.name}</span>
        <svg
          className={`w-4 h-4 transition-transform duration-200 ${isOpen ? 'rotate-180' : ''}`}
          fill="none"
          stroke="currentColor"
          viewBox="0 0 24 24"
        >
          <path
            strokeLinecap="round"
            strokeLinejoin="round"
            strokeWidth={2}
            d="M19 9l-7 7-7-7"
          />
        </svg>
      </button>

      {/* Dropdown */}
      {isOpen && (
        <div className="absolute right-0 mt-2 w-56 rounded-md shadow-lg bg-gray-800 ring-1 ring-black ring-opacity-5 z-50 animate-in fade-in-0 zoom-in-95 duration-200">
          <div className="py-1">
            <div className="px-4 py-2 text-xs font-semibold text-gray-400 uppercase tracking-wider">
              Switch Organization
            </div>
            
            {organizations
              .filter(org => org.id !== currentOrg.id)
              .map((org) => (
                <button
                  key={org.id}
                  onClick={() => handleOrgSwitch(org)}
                  className="flex items-center w-full px-4 py-2 text-left text-sm text-gray-300 hover:text-white hover:bg-gray-700 focus:outline-none focus:bg-gray-700 transition-colors duration-150"
                >
                  {org.icon_url && (
                    <img
                      src={org.icon_url}
                      alt={`${org.name} icon`}
                      className="w-5 h-5 rounded-full mr-3"
                    />
                  )}
                  <div className="flex-1 min-w-0">
                    <div className="truncate font-medium">{org.name}</div>
                    <div className="text-xs text-gray-400">/{org.prefix}</div>
                  </div>
                </button>
              ))}
            
            <div className="border-t border-gray-700 mt-1">
              <button
                onClick={handleViewAllOrgs}
                className="flex items-center w-full px-4 py-2 text-left text-sm text-gray-300 hover:text-white hover:bg-gray-700 focus:outline-none focus:bg-gray-700 transition-colors duration-150"
              >
                <svg
                  className="w-5 h-5 mr-3"
                  fill="none"
                  stroke="currentColor"
                  viewBox="0 0 24 24"
                >
                  <path
                    strokeLinecap="round"
                    strokeLinejoin="round"
                    strokeWidth={2}
                    d="M19 11H5m14 0a2 2 0 012 2v6a2 2 0 01-2 2H5a2 2 0 01-2-2v-6a2 2 0 012-2m14 0V9a2 2 0 00-2-2M5 11V9a2 2 0 012-2m0 0V5a2 2 0 012-2h6a2 2 0 012 2v2M7 7h10"
                  />
                </svg>
                View All Organizations
              </button>
              
              {/* SuperAdmin option - only show if user is superadmin */}
              {isSuperAdmin && (
                <button
                  onClick={handleSuperAdmin}
                  className="flex items-center w-full px-4 py-2 text-left text-sm text-yellow-300 hover:text-yellow-200 hover:bg-gray-700 focus:outline-none focus:bg-gray-700 transition-colors duration-150"
                >
                  <svg
                    className="w-5 h-5 mr-3"
                    fill="none"
                    stroke="currentColor"
                    viewBox="0 0 24 24"
                  >
                    <path
                      strokeLinecap="round"
                      strokeLinejoin="round"
                      strokeWidth={2}
                      d="M10.325 4.317c.426-1.756 2.924-1.756 3.35 0a1.724 1.724 0 002.573 1.066c1.543-.94 3.31.826 2.37 2.37a1.724 1.724 0 001.065 2.572c1.756.426 1.756 2.924 0 3.35a1.724 1.724 0 00-1.066 2.573c.94 1.543-.826 3.31-2.37 2.37a1.724 1.724 0 00-2.572 1.065c-.426 1.756-2.924 1.756-3.35 0a1.724 1.724 0 00-2.573-1.066c-1.543.94-3.31-.826-2.37-2.37a1.724 1.724 0 00-1.065-2.572c-1.756-.426-1.756-2.924 0-3.35a1.724 1.724 0 001.066-2.573c-.94-1.543.826-3.31 2.37-2.37.996.608 2.296.07 2.572-1.065z"
                    />
                    <path
                      strokeLinecap="round"
                      strokeLinejoin="round"
                      strokeWidth={2}
                      d="M15 12a3 3 0 11-6 0 3 3 0 016 0z"
                    />
                  </svg>
                  SuperAdmin Dashboard
                </button>
              )}
            </div>
          </div>
        </div>
      )}
    </div>
  );
};

export default OrganizationSwitcher; 