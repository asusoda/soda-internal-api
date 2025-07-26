import React, { useState } from "react";
import Sidebar from "../components/SideBar";
import apiClient from "../components/utils/axios";

const AddMerchandisePage = () => {
  const [isSidebarOpen, setIsSidebarOpen] = useState(false);
  const [imageUrl, setImageUrl] = useState("");
  const [name, setName] = useState("");
  const [price, setPrice] = useState("");
  const [stock, setStock] = useState(1);
  const [description, setDescription] = useState("");

  const handleSubmit = async (e) => {
    e.preventDefault();

    const productData = {
      name,
      description,
      price: parseInt(price),
      stock: parseInt(stock),
      image_url: imageUrl,
    };

    try {
      const response = await apiClient.post("/merch/products/add", productData);
      alert("Product added successfully!");
      // Reset form
      setImageUrl("");
      setName("");
      setPrice("");
      setStock(1);
      setDescription("");
    } catch (error) {
      console.error("Error submitting form:", error);
      alert("Something went wrong while adding the product.");
    }
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
          Add Product
        </h1>
        <form
          onSubmit={handleSubmit}
          className="space-y-6 max-w-md mx-auto bg-gray-800 p-6 rounded-xl shadow-lg"
        >
          <div>
            <label className="block text-lg font-semibold mb-2">
              Image URL
            </label>
            <input
              type="text"
              value={imageUrl}
              onChange={(e) => setImageUrl(e.target.value)}
              className="bg-gray-700 border border-gray-600 rounded p-2 w-full text-white"
              placeholder="Enter image URL"
            />
          </div>
          <div>
            <label className="block text-lg font-semibold mb-2">Name</label>
            <input
              type="text"
              value={name}
              onChange={(e) => setName(e.target.value)}
              className="bg-gray-700 border border-gray-600 rounded p-2 w-full text-white"
              placeholder="Enter product name"
              required
            />
          </div>
          <div>
            <label className="block text-lg font-semibold mb-2">
              Description
            </label>
            <textarea
              value={description}
              onChange={(e) => setDescription(e.target.value)}
              className="bg-gray-700 border border-gray-600 rounded p-2 w-full text-white"
              placeholder="Enter product description"
            />
          </div>
          <div>
            <label className="block text-lg font-semibold mb-2">Price</label>
            <input
              type="number"
              step="0.01"
              value={price}
              onChange={(e) => setPrice(e.target.value)}
              className="bg-gray-700 border border-gray-600 rounded p-2 w-full text-white"
              placeholder="e.g. 19.99"
              required
            />
          </div>
          <div>
            <label className="block text-lg font-semibold mb-2">Stock</label>
            <input
              type="number"
              value={stock}
              onChange={(e) => setStock(e.target.value)}
              className="bg-gray-700 border border-gray-600 rounded p-2 w-full text-white"
              placeholder="e.g. 100"
              required
            />
          </div>
          <div className="flex space-x-4 justify-end pt-4">
            <button
              type="submit"
              className="bg-blue-600 hover:bg-blue-700 text-white py-2 px-4 rounded"
            >
              Add Product
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
