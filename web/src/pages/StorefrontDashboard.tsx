import { useState, useEffect, useCallback } from "react";
import { useParams } from "react-router-dom";
import apiClient from "../components/utils/axios";
import OrganizationNavbar from "../components/shared/OrganizationNavbar";
import EditProductModal from "../components/editProductModal";
import { 
  FaBox, 
  FaPlus, 
  FaEdit, 
  FaTrash, 
  FaSpinner, 
  FaShoppingCart,
  FaEye,
  FaChartBar,
  FaExternalLinkAlt
} from "react-icons/fa";
import { toast } from "react-toastify";
import { useAuth } from "../components/auth/AuthContext";
import { Link } from "react-router-dom";
import { errorDetail, type Order, type Product } from "../storefrontTypes";

const StorefrontDashboard = () => {
  const { orgPrefix } = useParams();
  const { currentOrg } = useAuth();
  const [products, setProducts] = useState<Product[]>([]);
  const [orders, setOrders] = useState<Order[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [editingProduct, setEditingProduct] = useState<Product | null>(null);
  const [showEditModal, setShowEditModal] = useState(false);
  const [stats, setStats] = useState({
    totalProducts: 0,
    totalOrders: 0,
    totalRevenue: 0,
    lowStockProducts: 0
  });

  const fetchData = useCallback(async () => {
    const prefixToUse = orgPrefix || currentOrg?.prefix;
    if (!prefixToUse) {
      setError("No organization selected");
      setLoading(false);
      return;
    }

    setLoading(true);
    setError(null);
    try {
      // Fetch products and orders in parallel
      const [productsResponse, ordersResponse] = await Promise.all([
        apiClient.get<Product[]>(`/api/storefront/${prefixToUse}/products`),
        apiClient.get<Order[]>(`/api/storefront/${prefixToUse}/orders`)
      ]);

      const productsData = Array.isArray(productsResponse.data) ? productsResponse.data : [];
      const ordersData = Array.isArray(ordersResponse.data) ? ordersResponse.data : [];

      setProducts(productsData);
      setOrders(ordersData);

      // Calculate stats
      const totalRevenue = ordersData.reduce((sum, order) => sum + order.total_amount, 0);
      const lowStockProducts = productsData.filter(product => product.stock <= 5).length;

      setStats({
        totalProducts: productsData.length,
        totalOrders: ordersData.length,
        totalRevenue,
        lowStockProducts
      });

    } catch (err) {
      const errorMessage = `Failed to fetch data. ${errorDetail(err)}`;
      setError(errorMessage);
      toast.error(errorMessage);
      console.error("Error fetching dashboard data:", err);
    } finally {
      setLoading(false);
    }
  }, [orgPrefix, currentOrg?.prefix]);

  useEffect(() => {
    fetchData();
  }, [fetchData]);

  const handleEditProduct = (product: Product) => {
    setEditingProduct(product);
    setShowEditModal(true);
  };

  const handleDeleteProduct = async (productId: number) => {
    if (!window.confirm("Are you sure you want to delete this product?")) {
      return;
    }

    const prefixToUse = orgPrefix || currentOrg?.prefix;
    try {
      await apiClient.delete(`/api/storefront/${prefixToUse}/products/${productId}`);
      toast.success("Product deleted successfully!");
      fetchData(); // Refresh data
    } catch (err) {
      const errorMessage = `Failed to delete product: ${errorDetail(err)}`;
      toast.error(errorMessage);
      console.error("Error deleting product:", err);
    }
  };

  const handleUpdateOrderStatus = async (orderId: number, newStatus: string) => {
    const prefixToUse = orgPrefix || currentOrg?.prefix;
    try {
      await apiClient.put(`/api/storefront/${prefixToUse}/orders/${orderId}`, {
        status: newStatus
      });
      toast.success("Order status updated successfully!");
      fetchData(); // Refresh data
    } catch (err) {
      const errorMessage = `Failed to update order status: ${errorDetail(err)}`;
      toast.error(errorMessage);
      console.error("Error updating order status:", err);
    }
  };

  const getStatusColor = (status: string) => {
    switch (status) {
      case 'pending': return 'bg-yellow-600/50 text-yellow-100';
      case 'processing': return 'bg-blue-600/50 text-blue-100';
      case 'shipped': return 'bg-purple-600/50 text-purple-100';
      case 'delivered': return 'bg-green-600/50 text-green-100';
      case 'cancelled': return 'bg-red-600/50 text-red-100';
      default: return 'bg-gray-600/50 text-gray-100';
    }
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
      <div className="max-w-7xl mx-auto">
        {/* Header */}
        <div className="text-center mb-8">
          <h1 className="text-3xl font-bold mb-2">Storefront Dashboard</h1>
          <p className="text-gray-400">
            Manage products, orders, and view analytics for {(currentOrg || {name: 'the organization'}).name}
          </p>
          <div className="mt-4 flex justify-center space-x-4">
            <Link
              to={`/${orgPrefix || currentOrg?.prefix}/add-storefront-product`}
              className="bg-green-600 hover:bg-green-700 px-4 py-2 rounded-md transition-colors flex items-center"
            >
              <FaPlus className="mr-2" /> Add Product
            </Link>
            <a
              href={`${window.location.origin}/store/${orgPrefix || currentOrg?.prefix}`}
              target="_blank"
              rel="noopener noreferrer"
              className="bg-blue-600 hover:bg-blue-700 px-4 py-2 rounded-md transition-colors flex items-center"
            >
              <FaExternalLinkAlt className="mr-2" /> View Public Store
            </a>
          </div>
        </div>

        {error && (
          <div className="mb-6 p-4 bg-red-900/50 border border-red-500 rounded-md text-red-200">
            {error}
          </div>
        )}

        {loading ? (
          <div className="flex items-center justify-center py-12">
            <FaSpinner className="animate-spin text-pink-500 text-4xl" />
          </div>
        ) : (
          <>
            {/* Statistics Cards */}
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6 mb-8">
              <div className="bg-gray-900/50 backdrop-blur-sm rounded-xl border border-gray-700 p-6">
                <div className="flex items-center justify-between">
                  <div>
                    <p className="text-gray-400 text-sm">Total Products</p>
                    <p className="text-2xl font-bold text-white">{stats.totalProducts}</p>
                  </div>
                  <FaBox className="text-blue-400 text-2xl" />
                </div>
              </div>
              
              <div className="bg-gray-900/50 backdrop-blur-sm rounded-xl border border-gray-700 p-6">
                <div className="flex items-center justify-between">
                  <div>
                    <p className="text-gray-400 text-sm">Total Orders</p>
                    <p className="text-2xl font-bold text-white">{stats.totalOrders}</p>
                  </div>
                  <FaShoppingCart className="text-green-400 text-2xl" />
                </div>
              </div>
              
              <div className="bg-gray-900/50 backdrop-blur-sm rounded-xl border border-gray-700 p-6">
                <div className="flex items-center justify-between">
                  <div>
                    <p className="text-gray-400 text-sm">Total Revenue</p>
                    <p className="text-2xl font-bold text-white">{stats.totalRevenue.toFixed(2)}</p>
                  </div>
                  <FaChartBar className="text-yellow-400 text-2xl" />
                </div>
              </div>
              
              <div className="bg-gray-900/50 backdrop-blur-sm rounded-xl border border-gray-700 p-6">
                <div className="flex items-center justify-between">
                  <div>
                    <p className="text-gray-400 text-sm">Low Stock Items</p>
                    <p className="text-2xl font-bold text-white">{stats.lowStockProducts}</p>
                  </div>
                  <FaBox className="text-red-400 text-2xl" />
                </div>
              </div>
            </div>

            {/* Products Section */}
            <div className="bg-gray-900/50 backdrop-blur-sm rounded-xl border border-gray-700 p-6 mb-8">
              <div className="flex items-center justify-between mb-6">
                <h2 className="text-xl font-semibold flex items-center text-white">
                  <FaBox className="mr-2 text-blue-400" />
                  Products ({products.length})
                </h2>
              </div>

              {products.length === 0 ? (
                <div className="text-center py-8 text-gray-400">
                  No products found. <Link to={`/${orgPrefix || currentOrg?.prefix}/add-storefront-product`} className="text-blue-400 hover:underline">Add your first product</Link>
                </div>
              ) : (
                <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
                  {products.map((product) => (
                    <div key={product.id} className="bg-gray-800 rounded-lg border border-gray-700 p-4">
                      {product.image_url && (
                        <img
                          src={product.image_url}
                          alt={product.name}
                          className="w-full h-32 object-cover rounded-md mb-3"
                        />
                      )}
                      <h3 className="font-semibold text-white mb-2">{product.name}</h3>
                      {product.description && (
                        <p className="text-gray-400 text-sm mb-3 line-clamp-2">{product.description}</p>
                      )}
                      <div className="flex justify-between items-center mb-3">
                        <span className="text-lg font-bold text-green-400">
                          {product.price.toFixed(2)}
                        </span>
                        <span className={`text-sm px-2 py-1 rounded ${
                          product.stock <= 5 ? 'bg-red-600/50 text-red-100' : 'bg-green-600/50 text-green-100'
                        }`}>
                          {product.stock} in stock
                        </span>
                      </div>
                      <div className="flex space-x-2">
                        <button
                          onClick={() => handleEditProduct(product)}
                          className="flex-1 bg-blue-600 hover:bg-blue-700 px-3 py-2 rounded-md text-sm transition-colors flex items-center justify-center"
                        >
                          <FaEdit className="mr-1" /> Edit
                        </button>
                        <button
                          onClick={() => handleDeleteProduct(product.id)}
                          className="flex-1 bg-red-600 hover:bg-red-700 px-3 py-2 rounded-md text-sm transition-colors flex items-center justify-center"
                        >
                          <FaTrash className="mr-1" /> Delete
                        </button>
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </div>

            {/* Recent Orders Section */}
            <div className="bg-gray-900/50 backdrop-blur-sm rounded-xl border border-gray-700 p-6">
              <div className="flex items-center justify-between mb-6">
                <h2 className="text-xl font-semibold flex items-center text-white">
                  <FaShoppingCart className="mr-2 text-green-400" />
                  Recent Orders ({orders.length})
                </h2>
                <Link
                  to={`/${orgPrefix || currentOrg?.prefix}/transactions`}
                  className="bg-blue-600 hover:bg-blue-700 px-4 py-2 rounded-md text-sm transition-colors flex items-center"
                >
                  <FaEye className="mr-2" /> View All
                </Link>
              </div>

              {orders.length === 0 ? (
                <div className="text-center py-8 text-gray-400">
                  No orders found.
                </div>
              ) : (
                <div className="overflow-x-auto">
                  <table className="min-w-full border-collapse">
                    <thead className="text-gray-300 border-b border-gray-700">
                      <tr>
                        <th className="p-3 text-left font-medium">Order ID</th>
                        <th className="p-3 text-left font-medium">Customer</th>
                        <th className="p-3 text-left font-medium">Status</th>
                        <th className="p-3 text-left font-medium">Date</th>
                        <th className="p-3 text-right font-medium">Total</th>
                        <th className="p-3 text-center font-medium">Actions</th>
                      </tr>
                    </thead>
                    <tbody>
                      {orders.slice(0, 10).map((order) => (
                        <tr
                          key={order.id}
                          className="border-b border-gray-800 last:border-b-0"
                        >
                          <td className="p-3">#{order.id}</td>
                          <td className="p-3">{order.user_id}</td>
                          <td className="p-3">
                            <select
                              value={order.status}
                              onChange={(e) => handleUpdateOrderStatus(order.id, e.target.value)}
                              className={`px-2 py-1 rounded text-xs font-semibold bg-gray-700 border border-gray-600 ${getStatusColor(order.status)}`}
                            >
                              <option value="pending">Pending</option>
                              <option value="processing">Processing</option>
                              <option value="shipped">Shipped</option>
                              <option value="delivered">Delivered</option>
                              <option value="cancelled">Cancelled</option>
                            </select>
                          </td>
                          <td className="p-3 text-gray-400">
                            {new Date(order.created_at).toLocaleDateString()}
                          </td>
                          <td className="p-3 text-right font-bold text-white">
                            {order.total_amount.toFixed(2)}
                          </td>
                          <td className="p-3 text-center">
                            <span className="text-blue-400 text-sm">
                              {order.items?.length || 0} items
                            </span>
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}
            </div>
          </>
        )}

        {/* Edit Product Modal */}
        {showEditModal && editingProduct && (
          <EditProductModal
            product={editingProduct}
            onClose={() => {
              setShowEditModal(false);
              setEditingProduct(null);
            }}
            onProductUpdated={() => {
              fetchData();
              setShowEditModal(false);
              setEditingProduct(null);
            }}
            organizationPrefix={orgPrefix || currentOrg?.prefix}
          />
        )}
      </div>
    </OrganizationNavbar>
  );
};

export default StorefrontDashboard;
