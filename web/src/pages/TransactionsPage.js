import React, { useState } from "react";
import Sidebar from "../components/SideBar";

const TransactionsPage = () => {
  const [isSidebarOpen, setIsSidebarOpen] = useState(false);

  return (
    <div className="min-h-screen flex bg-gray-900 text-white">
      <Sidebar
        isSidebarOpen={isSidebarOpen}
        toggleSidebar={() => setIsSidebarOpen(!isSidebarOpen)}
      />
      <div
        className={`flex-1 p-8 transition-all duration-300 ${
          isSidebarOpen ? "ml-60" : "ml-16"
        }`}
      >
        <div className="flex items-center justify-between mb-6">
          <h1 className="text-4xl font-bold text-[#ba3554]">Transactions</h1>
          <select className="bg-gray-800 text-white border border-gray-600 rounded p-2">
            <option>Last 30 days</option>
            <option>Last 7 days</option>
            <option>Last 90 days</option>
          </select>
        </div>
        <div className="overflow-x-auto">
          <table className="w-full border-collapse bg-gray-800 rounded-xl overflow-hidden shadow-md">
            <thead className="bg-gray-700 text-white">
              <tr>
                <th className="p-3 text-left">Name</th>
                <th className="p-3 text-left">Email</th>
                <th className="p-3 text-left">ASU ID</th>
                <th className="p-3 text-left">Item Bought</th>
                <th className="p-3 text-left">Date</th>
                <th className="p-3 text-right">Cost</th>
              </tr>
            </thead>
            <tbody>
              <tr className="bg-gray-600 hover:bg-gray-500 transition-colors">
                <td className="p-3">Justin Lee</td>
                <td className="p-3">jlee824@asu.edu</td>
                <td className="p-3">1228576195</td>
                <td className="p-3">ASU Shirt</td>
                <td className="p-3">5/18/2025</td>
                <td className="p-3 text-right">300</td>
              </tr>
              {/* Add more rows as needed */}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
};

export default TransactionsPage;
