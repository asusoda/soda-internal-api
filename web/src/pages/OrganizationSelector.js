import React from 'react';
import { useAuth } from '../components/auth/AuthContext';
import { useNavigate } from 'react-router-dom';
import Orb from '../components/ui/Orb';

const OrganizationSelector = () => {
  const { organizations, selectOrganization, user, logout, isSuperAdmin } = useAuth();
  const navigate = useNavigate();

  const handleOrganizationSelect = (org) => {
    selectOrganization(org);
    navigate(`/${org.prefix}/dashboard`);
  };

  return (
    <div className="relative min-h-screen bg-black text-white overflow-hidden">
      {/* Background Effects */}
      <div className="absolute inset-0">
        <Orb hue={300} forceHoverState={true} hoverIntensity={0.1} />
      </div>

      {/* Main Content */}
      <div className="relative z-10 min-h-screen flex items-center justify-center">
        <div className="max-w-md w-full space-y-8">
          <div>
            <h2 className="mt-6 text-center text-3xl font-extrabold text-white">
              Select Organization
            </h2>
            <p className="mt-2 text-center text-sm text-gray-400">
              Welcome, {user?.name}! Choose an organization to continue.
            </p>
          </div>
          
          <div className="space-y-4">
            {/* SuperAdmin Dashboard Option */}
            {isSuperAdmin && (
              <div
                onClick={() => navigate('/superadmin')}
                className="relative block w-full border-2 border-yellow-500 border-dashed rounded-lg p-6 text-center hover:border-yellow-400 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-yellow-500 cursor-pointer transition-colors bg-yellow-900 bg-opacity-20 hover:bg-opacity-30"
              >
                <div className="flex items-center justify-center space-x-3">
                  <svg
                    className="w-10 h-10 text-yellow-400"
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
                  <div className="text-left">
                    <h3 className="text-lg font-medium text-yellow-300">
                      SuperAdmin Dashboard
                    </h3>
                    <p className="text-sm text-yellow-400">
                      Manage all organizations and system settings
                    </p>
                  </div>
                </div>
              </div>
            )}

            {organizations.length === 0 ? (
              <div className="text-center">
                <p className="text-gray-400 mb-4">
                  You don't have access to any organizations.
                </p>
                <button
                  onClick={logout}
                  className="inline-flex justify-center py-2 px-4 border border-transparent shadow-sm text-sm font-medium rounded-md text-white bg-red-600 hover:bg-red-700 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-red-500"
                >
                  Logout
                </button>
              </div>
            ) : (
              <>
                {organizations.map((org) => (
                  <div
                    key={org.id}
                    onClick={() => handleOrganizationSelect(org)}
                    className="relative block w-full border-2 border-gray-600 border-dashed rounded-lg p-6 text-center hover:border-gray-400 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-indigo-500 cursor-pointer transition-colors bg-gray-800 hover:bg-gray-700"
                  >
                    <div className="flex items-center justify-center space-x-3">
                      {org.icon_url && (
                        <img
                          src={org.icon_url}
                          alt={`${org.name} icon`}
                          className="w-10 h-10 rounded-full"
                        />
                      )}
                      <div className="text-left">
                        <h3 className="text-lg font-medium text-white">
                          {org.name}
                        </h3>
                        {org.description && (
                          <p className="text-sm text-gray-400">
                            {org.description}
                          </p>
                        )}
                        <p className="text-xs text-gray-500 mt-1">
                          /{org.prefix}
                        </p>
                      </div>
                    </div>
                  </div>
                ))}
                
                <div className="text-center mt-6">
                  <button
                    onClick={logout}
                    className="text-sm text-gray-400 hover:text-white underline"
                  >
                    Logout
                  </button>
                </div>
              </>
            )}
          </div>
        </div>
      </div>
    </div>
  );
};

export default OrganizationSelector;