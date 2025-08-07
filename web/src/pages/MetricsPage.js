import React from "react";
import OrganizationNavbar from "../components/shared/OrganizationNavbar";

const MetricsPage = () => {
  return (
    <OrganizationNavbar>
      <div className="max-w-6xl mx-auto">
        <div className="text-center mb-8">
          <h1 className="text-3xl font-bold mb-2">Metrics</h1>
          <p className="text-gray-400">
            View system metrics and user engagement statistics
          </p>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
          <div className="bg-gray-900/50 backdrop-blur-sm rounded-xl border border-gray-700 p-6">
            <h2 className="text-2xl font-semibold mb-4 text-white">User Engagement</h2>
            <div className="space-y-3">
              <div className="flex justify-between items-center">
                <span className="text-gray-300">Items Redeemed this semester:</span>
                <span className="text-white font-bold">10</span>
              </div>
              <div className="flex justify-between items-center">
                <span className="text-gray-300">Number of Soda Caps redeemed:</span>
                <span className="text-white font-bold">100</span>
              </div>
              <div className="flex justify-between items-center">
                <span className="text-gray-300">Unique members last 30 days:</span>
                <span className="text-white font-bold">5</span>
              </div>
              <div className="flex justify-between items-center">
                <span className="text-gray-300">Redeeming member rate:</span>
                <span className="text-white font-bold">50%</span>
              </div>
            </div>
          </div>

          <div className="bg-gray-900/50 backdrop-blur-sm rounded-xl border border-gray-700 p-6">
            <h2 className="text-2xl font-semibold mb-4 text-white">System Health</h2>
            <div className="space-y-3">
              <div className="flex justify-between items-center">
                <span className="text-gray-300">API Error Rate:</span>
                <span className="text-green-400 font-bold">1%</span>
              </div>
              <div className="flex justify-between items-center">
                <span className="text-gray-300">API Response Time:</span>
                <span className="text-white font-bold">117 ms</span>
              </div>
            </div>
          </div>
        </div>
      </div>
    </OrganizationNavbar>
  );
};

export default MetricsPage;
