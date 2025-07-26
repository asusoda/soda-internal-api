// src/pages/MerchListPage.jsx
import React, { useState, useEffect, useCallback } from "react"; // Add useCallback
import Sidebar from "../components/SideBar";
import apiClient from "../components/utils/axios";
import EditProductModal from "../components/editProductModal"; // Import the modal component

const MerchListPage = () => {
  const [isSidebarOpen, setIsSidebarOpen] = useState(false);
  const [products, setProducts] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  // State for modal
  const [isModalOpen, setIsModalOpen] = useState(false);
  const [selectedProduct, setSelectedProduct] = useState(null);

  // Memoize fetchProducts to avoid unnecessary re-creations
  const fetchProducts = useCallback(async () => {
    try {
      setLoading(true);
      const response = await apiClient.get("/merch/products");
      setProducts(response.data || []);
      setError(null); // Clear any previous errors on successful fetch
    } catch (err) {
      setError(err.message);
      console.error("Failed to fetch products:", err);
    } finally {
      setLoading(false);
    }
  }, []); // Dependencies array is empty as it doesn't depend on outside state

  useEffect(() => {
    fetchProducts();
  }, [fetchProducts]); // Run on mount and if fetchProducts function itself changes (rare with useCallback)

  const handleDelete = async (productId) => {
    if (!window.confirm("Are you sure you want to delete this product?"))
      return;

    try {
      await apiClient.delete(`/merch/products/${productId}`);
      setProducts(products.filter((product) => product.id !== productId));
      alert("Product deleted successfully");
    } catch (err) {
      console.error("Failed to delete product:", err);
      alert("Failed to delete product");
    }
  };

  // Handlers for modal
  const handleEditClick = (product) => {
    setSelectedProduct(product);
    setIsModalOpen(true);
  };

  const handleCloseModal = () => {
    setIsModalOpen(false);
    setSelectedProduct(null); // Clear selected product
  };

  const handleProductUpdated = () => {
    // When a product is updated in the modal, re-fetch the list to show changes
    fetchProducts();
  };

  if (loading) return <div className="text-white p-8">Loading products...</div>;
  if (error) return <div className="text-red-500 p-8">Error: {error}</div>;

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
          Merchandise List
        </h1>

        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
          {products.map((product) => (
            <div
              key={product.id}
              className="bg-gray-800 rounded-lg overflow-hidden shadow-lg"
            >
              {product.image_url && (
                <img
                  src={product.image_url}
                  alt={product.name}
                  className="w-full h-48 object-cover"
                  onError={(e) => {
                    e.target.src =
                      "https://via.placeholder.com/300x200?text=No+Image";
                  }}
                />
              )}
              <div className="p-4">
                <h2 className="text-xl font-semibold mb-2">{product.name}</h2>
                <p className="text-gray-300 mb-2">{product.description}</p>
                <div className="flex justify-between items-center mb-2">
                  <span className="text-lg font-bold">
                    {product.price} Soda Caps
                  </span>
                  <span className="text-sm bg-gray-700 px-2 py-1 rounded">
                    Stock: {product.stock}
                  </span>
                </div>
                <div className="flex space-x-2 mt-4">
                  <button
                    onClick={() => handleEditClick(product)} // <--- Changed this line
                    className="bg-blue-600 hover:bg-blue-700 text-white py-1 px-3 rounded text-sm"
                  >
                    Edit
                  </button>
                  <button
                    onClick={() => handleDelete(product.id)}
                    className="bg-red-600 hover:bg-red-700 text-white py-1 px-3 rounded text-sm"
                  >
                    Delete
                  </button>
                </div>
              </div>
            </div>
          ))}
        </div>

        {products.length === 0 && (
          <div className="text-center py-8">
            <p className="text-xl">No products found</p>
            <button
              onClick={() => (window.location.href = "/merch/products/add")}
              className="mt-4 bg-green-600 hover:bg-green-700 text-white py-2 px-4 rounded"
            >
              Add New Product
            </button>
          </div>
        )}
      </div>

      {/* Render the modal component if isModalOpen is true */}
      {isModalOpen && (
        <EditProductModal
          product={selectedProduct}
          onClose={handleCloseModal}
          onProductUpdated={handleProductUpdated}
        />
      )}
    </div>
  );
};

export default MerchListPage;
