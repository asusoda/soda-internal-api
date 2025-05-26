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
        className={`flex-1 p-8 ${
          isSidebarOpen ? "ml-60" : "ml-16"
        } bg-white text-black`}
      >
        <div className="flex items-center justify-between mb-6">
          <h1 className="text-4xl font-bold">Merchandise</h1>
          <a
            href="/add-merchandise"
            className="bg-blue-600 hover:bg-blue-700 text-white py-2 px-4 rounded"
          >
            Add Item
          </a>
        </div>
        <table className="w-full border-collapse">
          <thead className="bg-gray-200">
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
            <tr className="bg-gray-100">
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
              <td className="p-3 text-blue-600 hover:underline cursor-pointer">
                Edit
              </td>
              <td className="p-3 text-red-600 hover:bg-red-100 cursor-pointer">
                🗑️
              </td>
            </tr>
          </tbody>
        </table>
      </div>
    </div>
  );
};

export default MerchandiseListPage;
