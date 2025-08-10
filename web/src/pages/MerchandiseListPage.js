import React, { useState, useEffect, useCallback } from "react";
import apiClient from "../components/utils/axios";
import OrganizationNavbar from "../components/shared/OrganizationNavbar";
import EditProductModal from "../components/editProductModal";
import { FaBox, FaPlus } from "react-icons/fa"; // Import relevant icons
import { toast } from "react-toastify";
import { useNavigate } from "react-router-dom";
import { useAuth } from "../components/auth/AuthContext";

const MerchListPage = () => {
  const { currentOrg } = useAuth();
  const [products, setProducts] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const navigate = useNavigate();

  const [isModalOpen, setIsModalOpen] = useState(false);
  const [selectedProduct, setSelectedProduct] = useState(null);

  const fetchProducts = useCallback(async () => {
    if (!currentOrg?.prefix) {
      setError("No organization selected");
      setLoading(false);
      return;
    }

    try {
      setLoading(true);
      const response = await apiClient.get(`/api/merch/${currentOrg.prefix}/products`);
      setProducts(response.data || []);
      setError(null);
    } catch (err) {
      const errorMessage = "Failed to fetch products: Network Error";
      setError(errorMessage);
      toast.error(errorMessage);
      console.error("Failed to fetch products:", err);
    } finally {
      setLoading(false);
    }
  }, [currentOrg?.prefix]);

  useEffect(() => {
    fetchProducts();
  }, [fetchProducts]);

  const handleDelete = async (productId) => {
    if (!currentOrg?.prefix) {
      toast.error("No organization selected");
      return;
    }

    if (!window.confirm("Are you sure you want to delete this product?"))
      return;

    try {
      await apiClient.delete(`/api/merch/${currentOrg.prefix}/products/${productId}`);
      setProducts(products.filter((product) => product.id !== productId));
      toast.success("Product deleted successfully");
    } catch (err) {
      console.error("Failed to delete product:", err);
      toast.error("Failed to delete product");
    }
  };

  const handleEditClick = (product) => {
    setSelectedProduct(product);
    setIsModalOpen(true);
  };

  const handleCloseModal = () => {
    setIsModalOpen(false);
    setSelectedProduct(null);
  };

  const handleProductUpdated = () => {
    fetchProducts();
  };

  const handleAddNewProduct = () => {
    navigate("/merch/products/add");
  };

  if (!currentOrg) {
    return (
      <OrganizationNavbar>
        <div className="text-center">
          <p className="text-gray-400">Please select an organization to continue.</p>
        </div>
      </OrganizationNavbar>
    );
  }

  return (
    <OrganizationNavbar>
      <div className="max-w-6xl mx-auto">
        <div className="text-center mb-8">
          <h1 className="text-3xl font-bold mb-2">Merchandise List</h1>
          <p className="text-gray-400">
            View, edit, and delete merchandise products for {currentOrg.name}
          </p>
        </div>

        {error && (
          <div className="mb-6 p-4 bg-red-900/50 border border-red-500 rounded-md text-red-200">
            {error}
          </div>
        )}

        <div className="bg-gray-900/50 backdrop-blur-sm rounded-xl border border-gray-700 p-6">
          <h2 className="text-xl font-semibold mb-4 flex items-center">
            <FaBox className="mr-2 text-pink-400" />
            Available Products
          </h2>

          {loading ? (
            <div className="flex items-center justify-center py-12">
              <div className="text-center">
                <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-pink-500 mx-auto mb-4"></div>
                <p className="text-gray-400">Loading products...</p>
              </div>
            </div>
          ) : products.length === 0 ? (
            <div className="text-center py-12">
              <p className="text-gray-400">No products found</p>
              <button
                onClick={handleAddNewProduct}
                className="mt-4 px-4 py-2 bg-pink-600 hover:bg-pink-700 text-white rounded-md transition-colors flex items-center justify-center mx-auto"
              >
                <FaPlus className="mr-2" /> Add New Product
              </button>
            </div>
          ) : (
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
              {products.map((product) => (
                <div
                  key={product.id}
                  className="bg-gray-800 rounded-lg overflow-hidden shadow-lg border border-gray-700"
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
                    <h3 className="text-lg font-semibold text-white mb-2">
                      {product.name}
                    </h3>
                    <p className="text-gray-400 text-sm mb-2 line-clamp-3">
                      {product.description}
                    </p>
                    <div className="flex justify-between items-center mb-4">
                      <span className="text-lg font-bold text-white">
                        {product.price} Soda Caps
                      </span>
                      <span className="text-sm bg-gray-700 px-2 py-1 rounded text-gray-300">
                        Stock: {product.stock}
                      </span>
                    </div>
                    <div className="flex space-x-2">
                      <button
                        onClick={() => handleEditClick(product)}
                        className="flex-1 bg-blue-600 hover:bg-blue-700 text-white py-1 px-3 rounded text-sm transition-colors"
                      >
                        Edit
                      </button>
                      <button
                        onClick={() => handleDelete(product.id)}
                        className="flex-1 bg-red-600 hover:bg-red-700 text-white py-1 px-3 rounded text-sm transition-colors"
                      >
                        Delete
                      </button>
                    </div>
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      </div>

      {isModalOpen && (
        <EditProductModal
          product={selectedProduct}
          onClose={handleCloseModal}
          onProductUpdated={handleProductUpdated}
          organizationPrefix={currentOrg.prefix}
        />
      )}
    </OrganizationNavbar>
  );
};

export default MerchListPage;
