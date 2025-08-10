import React, { useState, useEffect } from "react";
import apiClient from "./utils/axios"; // Adjust path if necessary
import { toast } from "react-toastify";

const EditProductModal = ({ product, onClose, onProductUpdated, organizationPrefix }) => {
  const [formData, setFormData] = useState({
    name: "",
    description: "",
    price: "",
    stock: "",
    image_url: "",
  });
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);

  useEffect(() => {
    // Populate form data when the product prop changes (i.e., when modal opens for a new product)
    if (product) {
      setFormData({
        name: product.name,
        description: product.description,
        price: product.price,
        stock: product.stock,
        image_url: product.image_url,
      });
    }
  }, [product]);

  const handleChange = (e) => {
    const { name, value } = e.target;
    setFormData((prevData) => ({
      ...prevData,
      [name]: name === "price" || name === "stock" ? Number(value) : value,
    }));
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    
    if (!organizationPrefix) {
      toast.error("No organization selected");
      return;
    }
    
    setLoading(true);
    setError(null);
    try {
      await apiClient.put(`/api/merch/${organizationPrefix}/products/${product.id}`, formData);
      toast.success("Product updated successfully!");
      onProductUpdated(); // Notify parent component to refresh products
      onClose(); // Close the modal
    } catch (err) {
      const errorMessage = "Failed to update product. " +
        (err.response?.data?.error || err.message);
      setError(errorMessage);
      toast.error(errorMessage);
      console.error("Failed to update product:", err);
    } finally {
      setLoading(false);
    }
  };

  if (!product) return null; // Don't render if no product is passed

  return (
    <div className="fixed inset-0 bg-black bg-opacity-75 flex items-center justify-center z-50">
      <div className="bg-gray-800 p-8 rounded-lg shadow-xl max-w-lg w-full text-white relative">
        <button
          onClick={onClose}
          className="absolute top-4 right-4 text-gray-400 hover:text-white text-2xl"
        >
          &times;
        </button>
        <h2 className="text-3xl font-bold mb-6 text-center text-[#ba3554]">
          Edit Product: {product.name}
        </h2>

        {error && <p className="text-red-500 mb-4 text-center">{error}</p>}

        <form onSubmit={handleSubmit}>
          <div className="mb-4">
            <label
              htmlFor="name"
              className="block text-gray-300 text-sm font-bold mb-2"
            >
              Product Name:
            </label>
            <input
              type="text"
              id="name"
              name="name"
              value={formData.name}
              onChange={handleChange}
              className="shadow appearance-none border rounded w-full py-2 px-3 text-white leading-tight focus:outline-none focus:shadow-outline bg-gray-700 border-gray-600"
              required
            />
          </div>
          <div className="mb-4">
            <label
              htmlFor="description"
              className="block text-gray-300 text-sm font-bold mb-2"
            >
              Description:
            </label>
            <textarea
              id="description"
              name="description"
              value={formData.description}
              onChange={handleChange}
              className="shadow appearance-none border rounded w-full py-2 px-3 text-white leading-tight focus:outline-none focus:shadow-outline bg-gray-700 border-gray-600 h-24"
            ></textarea>
          </div>
          <div className="mb-4">
            <label
              htmlFor="price"
              className="block text-gray-300 text-sm font-bold mb-2"
            >
              Price:
            </label>
            <input
              type="number"
              id="price"
              name="price"
              value={formData.price}
              onChange={handleChange}
              className="shadow appearance-none border rounded w-full py-2 px-3 text-white leading-tight focus:outline-none focus:shadow-outline bg-gray-700 border-gray-600"
              step="0.01"
              required
            />
          </div>
          <div className="mb-4">
            <label
              htmlFor="stock"
              className="block text-gray-300 text-sm font-bold mb-2"
            >
              Stock:
            </label>
            <input
              type="number"
              id="stock"
              name="stock"
              value={formData.stock}
              onChange={handleChange}
              className="shadow appearance-none border rounded w-full py-2 px-3 text-white leading-tight focus:outline-none focus:shadow-outline bg-gray-700 border-gray-600"
              required
            />
          </div>
          <div className="mb-6">
            <label
              htmlFor="image_url"
              className="block text-gray-300 text-sm font-bold mb-2"
            >
              Image URL:
            </label>
            <input
              type="text"
              id="image_url"
              name="image_url"
              value={formData.image_url}
              onChange={handleChange}
              className="shadow appearance-none border rounded w-full py-2 px-3 text-white leading-tight focus:outline-none focus:shadow-outline bg-gray-700 border-gray-600"
            />
            {formData.image_url && (
              <img
                src={formData.image_url}
                alt="Product Preview"
                className="mt-4 w-24 h-24 object-cover rounded mx-auto"
              />
            )}
          </div>
          <div className="flex items-center justify-center space-x-4">
            <button
              type="submit"
              className="bg-blue-600 hover:bg-blue-700 text-white font-bold py-2 px-4 rounded focus:outline-none focus:shadow-outline"
              disabled={loading}
            >
              {loading ? "Updating..." : "Update Product"}
            </button>
            <button
              type="button"
              onClick={onClose}
              className="bg-gray-600 hover:bg-gray-700 text-white font-bold py-2 px-4 rounded focus:outline-none focus:shadow-outline"
            >
              Cancel
            </button>
          </div>
        </form>
      </div>
    </div>
  );
};

export default EditProductModal;
