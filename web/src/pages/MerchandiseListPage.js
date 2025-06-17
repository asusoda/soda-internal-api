import React, { useState } from "react";
import Sidebar from "../components/SideBar";

const MerchandiseListPage = () => {
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
        <h1 className="text-4xl font-bold text-center text-[#e11d48] mb-8">
          Merchandise
        </h1>

        <div className="bg-[#1e293b] p-6 rounded-lg shadow-md">
          <div className="flex justify-between items-center mb-6">
            <h2 className="text-2xl font-semibold">Item List</h2>
            <a
              href="/add-merchandise"
              className="bg-blue-600 hover:bg-blue-700 text-white py-2 px-4 rounded"
            >
              Add Item
            </a>
          </div>

          <table className="w-full border-collapse">
            <thead className="bg-[#334155] text-white">
              <tr>
                <th className="p-3 text-left">Image</th>
                <th className="p-3 text-left">Name</th>
                <th className="p-3 text-right">Cap Cost</th>
                <th className="p-3 text-left">Visibility</th>
                <th className="p-3 text-left">Update</th>
                <th className="p-3 text-left">Delete</th>
              </tr>
            </thead>
            <tbody>
              <tr className="bg-[#475569]">
                <td className="p-3">
                  <img
                    src="/asu-hoodie.png"
                    alt="ASU Hoodie"
                    className="w-16 h-16 rounded"
                  />
                </td>
                <td className="p-3">ASU shirt</td>
                <td className="p-3 text-right">100</td>
                <td className="p-3">Hidden</td>
                <td className="p-3 text-blue-400 hover:underline cursor-pointer">
                  Edit
                </td>
                <td className="p-3 text-red-400 hover:text-red-300 cursor-pointer">
                  🗑️
                </td>
              </tr>
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
};

export default MerchandiseListPage;
