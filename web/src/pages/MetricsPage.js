import React, { useState } from "react";
import Sidebar from "../components/SideBar";

const MetricsPage = () => {
  const [isSidebarOpen, setIsSidebarOpen] = useState(false);

  return (
    <div className="min-h-screen flex bg-gray-900 text-white">
      <Sidebar
        isSidebarOpen={isSidebarOpen}
        toggleSidebar={() => setIsSidebarOpen(!isSidebarOpen)}
      />
      <div
        className={`flex-1 p-8 ${
          isSidebarOpen ? "ml-60" : "ml-16"
        } bg-white text-black`}
      >
        <h1 className="text-4xl font-bold mb-6">Metrics</h1>
        <div className="space-y-6 max-w-md">
          <div>
            <h2 className="text-2xl font-semibold mb-2">User Engagement</h2>
            <ul className="list-disc list-inside">
              <li>Items Redeemed this semester: 10</li>
              <li>Number of Soda Caps redeemed: 100</li>
              <li>Unique members last 30 days: 5</li>
              <li>Redeeming member rate: 50%</li>
            </ul>
          </div>
          <div>
            <h2 className="text-2xl font-semibold mb-2">System Health</h2>
            <ul className="list-disc list-inside">
              <li>API Error Rate: 1%</li>
              <li>API Response Time: 117 ms</li>
            </ul>
          </div>
        </div>
      </div>
    </div>
  );
};

export default MetricsPage;
