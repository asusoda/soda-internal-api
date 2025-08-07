import React, { useState } from "react";
import apiClient from "../components/utils/axios";
import OrganizationNavbar from "../components/shared/OrganizationNavbar";
import { FaBox, FaPlus } from "react-icons/fa";
import { toast } from "react-toastify";

const AddMerchandisePage = () => {
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
      price: parseFloat(price), // Use parseFloat for decimal prices
      stock: parseInt(stock),
      image_url: imageUrl,
    };

    try {
      // Updated API endpoint to match the new structure
      const response = await apiClient.post("/api/merch/products", productData);
      toast.success("Product added successfully!");
      // Reset form
      setImageUrl("");
      setName("");
      setPrice("");
      setStock(1);
      setDescription("");
    } catch (error) {
      console.error("Error submitting form:", error);
      const errorMessage = error.response?.data?.message ||
        "Something went wrong while adding the product.";
      toast.error(errorMessage);
    }
  };

  return (
    <OrganizationNavbar>
      <div className="max-w-xl mx-auto">
        <div className="text-center mb-8">
          <h1 className="text-3xl font-bold mb-2">Add New Product</h1>
          <p className="text-gray-400">
            Add a new item to your merchandise store
          </p>
        </div>

        <div className="bg-gray-900/50 backdrop-blur-sm rounded-xl border border-gray-700 p-6">
          <h2 className="text-xl font-semibold mb-4 flex items-center text-white">
            <FaPlus className="mr-2 text-green-400" />
            Product Details
          </h2>

          <form onSubmit={handleSubmit} className="space-y-4">
            <div>
              <label className="block text-sm font-medium text-gray-300 mb-1">
                Product Name <span className="text-red-500">*</span>
              </label>
              <input
                type="text"
                value={name}
                onChange={(e) => setName(e.target.value)}
                className="w-full px-3 py-2 bg-gray-800 border border-gray-600 rounded-md text-white placeholder-gray-400 focus:outline-none focus:border-green-500"
                placeholder="e.g., Club T-Shirt"
                required
              />
            </div>

            <div>
              <label className="block text-sm font-medium text-gray-300 mb-1">
                Description
              </label>
              <textarea
                value={description}
                onChange={(e) => setDescription(e.target.value)}
                className="w-full px-3 py-2 bg-gray-800 border border-gray-600 rounded-md text-white placeholder-gray-400 focus:outline-none focus:border-green-500"
                placeholder="A brief description of the product."
                rows="3"
              />
            </div>

            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              <div>
                <label className="block text-sm font-medium text-gray-300 mb-1">
                  Price <span className="text-red-500">*</span>
                </label>
                <input
                  type="number"
                  step="0.01"
                  value={price}
                  onChange={(e) => setPrice(e.target.value)}
                  className="w-full px-3 py-2 bg-gray-800 border border-gray-600 rounded-md text-white placeholder-gray-400 focus:outline-none focus:border-green-500"
                  placeholder="e.g., 20.00"
                  required
                />
              </div>

              <div>
                <label className="block text-sm font-medium text-gray-300 mb-1">
                  Stock <span className="text-red-500">*</span>
                </label>
                <input
                  type="number"
                  value={stock}
                  onChange={(e) => setStock(e.target.value)}
                  className="w-full px-3 py-2 bg-gray-800 border border-gray-600 rounded-md text-white placeholder-gray-400 focus:outline-none focus:border-green-500"
                  placeholder="e.g., 50"
                  required
                />
              </div>
            </div>

            <div>
              <label className="block text-sm font-medium text-gray-300 mb-1">
                Image URL
              </label>
              <input
                type="text"
                value={imageUrl}
                onChange={(e) => setImageUrl(e.target.value)}
                className="w-full px-3 py-2 bg-gray-800 border border-gray-600 rounded-md text-white placeholder-gray-400 focus:outline-none focus:border-green-500"
                placeholder="https://example.com/image.jpg"
              />
            </div>

            <div className="flex space-x-4 pt-4">
              <button
                type="submit"
                className="flex-1 px-4 py-2 bg-green-600 hover:bg-green-700 rounded-md text-white font-medium transition-colors flex items-center justify-center"
              >
                <FaPlus className="mr-2" /> Add Product
              </button>
              <button
                type="button"
                onClick={() => window.history.back()}
                className="flex-1 px-4 py-2 bg-gray-600 hover:bg-gray-700 rounded-md text-white font-medium transition-colors"
              >
                Cancel
              </button>
            </div>
          </form>
        </div>
      </div>
    </OrganizationNavbar>
  );
};

export default AddMerchandisePage;
