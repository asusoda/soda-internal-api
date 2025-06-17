import React, { useState } from "react";
import Sidebar from "../components/SideBar";

const AddMerchandisePage = () => {
  const [isSidebarOpen, setIsSidebarOpen] = useState(false);
  const [imageFile, setImageFile] = useState(null);
  const [name, setName] = useState("");
  const [cost, setCost] = useState("");
  const [visibility, setVisibility] = useState("Shown");

  const handleSubmit = (e) => {
    e.preventDefault();
    // TODO: send to API
  };

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
        <h1 className="text-4xl font-bold mb-6 text-center text-[#ba3554]">
          Add Merchandise
        </h1>
        <form
          onSubmit={handleSubmit}
          className="space-y-6 max-w-md mx-auto bg-gray-800 p-6 rounded-xl shadow-lg"
        >
          <div>
            <label className="block text-lg font-semibold mb-2">Image</label>
            <input
              type="file"
              accept="image/*"
              onChange={(e) => setImageFile(e.target.files[0])}
              className="bg-gray-700 border border-gray-600 rounded p-2 w-full text-white"
            />
          </div>
          <div>
            <label className="block text-lg font-semibold mb-2">Name</label>
            <input
              type="text"
              value={name}
              onChange={(e) => setName(e.target.value)}
              className="bg-gray-700 border border-gray-600 rounded p-2 w-full text-white"
              placeholder="Enter item name"
              required
            />
          </div>
          <div>
            <label className="block text-lg font-semibold mb-2">Cost</label>
            <input
              type="number"
              value={cost}
              onChange={(e) => setCost(e.target.value)}
              className="bg-gray-700 border border-gray-600 rounded p-2 w-full text-white"
              placeholder="e.g. 100"
              required
            />
          </div>
          <div>
            <label className="block text-lg font-semibold mb-2">
              Visibility
            </label>
            <select
              value={visibility}
              onChange={(e) => setVisibility(e.target.value)}
              className="bg-gray-700 border border-gray-600 rounded p-2 w-full text-white"
            >
              <option>Shown</option>
              <option>Hidden</option>
            </select>
          </div>
          <div className="flex space-x-4 justify-end pt-4">
            <button
              type="submit"
              className="bg-blue-600 hover:bg-blue-700 text-white py-2 px-4 rounded"
            >
              Add Item
            </button>
            <button
              type="button"
              onClick={() => window.history.back()}
              className="bg-red-600 hover:bg-red-700 text-white py-2 px-4 rounded"
            >
              Cancel
            </button>
          </div>
        </form>
      </div>
    </div>
  );
};

export default AddMerchandisePage;
