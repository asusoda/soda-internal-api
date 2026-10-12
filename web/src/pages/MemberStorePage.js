import React, { useState, useEffect, useCallback } from "react";
import { useParams } from "react-router-dom";
import apiClient from "../components/utils/axios";
import { FaShoppingCart, FaPlus, FaMinus, FaSpinner, FaCheck, FaUser, FaHistory, FaCoins, FaStore, FaEnvelope, FaTachometerAlt, FaSignOutAlt } from "react-icons/fa";
import { toast } from "react-toastify";

const MemberStorePage = () => {
  const { orgPrefix } = useParams();
  const [organization, setOrganization] = useState(null);
  const [products, setProducts] = useState([]);
  const [orders, setOrders] = useState([]);
  const [userPoints, setUserPoints] = useState(0);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [cart, setCart] = useState([]);
  const [activeTab, setActiveTab] = useState('store');
  const [isProcessingOrder, setIsProcessingOrder] = useState(false);
  const [isAuthenticated, setIsAuthenticated] = useState(false);
  const [memberProfile, setMemberProfile] = useState(null);

  const checkMemberSession = useCallback(() => {
    const memberUser = localStorage.getItem('memberUser');
    const memberOrg = localStorage.getItem('memberOrg');
    
    if (memberUser && memberOrg) {
      const org = JSON.parse(memberOrg);
      
      if (org.prefix === orgPrefix) {
        setIsAuthenticated(true);
        return true;
      }
    }
    return false;
  }, [orgPrefix]);

  const fetchUserPoints = useCallback(async () => {
    // Callers run this only after the member has signed in.
    if (!orgPrefix) return;
    
    try {
      const response = await apiClient.get(`/api/points/${orgPrefix}/member_profile`);
      setMemberProfile(response.data);
      setUserPoints(response.data.current_organization?.points || 0);
    } catch (err) {
      console.log("Could not fetch member profile:", err);
    }
  }, [orgPrefix]);

  const checkAuthentication = useCallback(async () => {
    // First check member session
    if (checkMemberSession()) {
      try {
        // If member session exists, try to get orders using member API
        const memberUser = JSON.parse(localStorage.getItem('memberUser'));
        const response = await apiClient.post(`/api/storefront/${orgPrefix}/members/orders`, {}, {
          headers: {
            'X-Member-User-Id': memberUser.id
          }
        });
        setOrders(Array.isArray(response.data) ? response.data : []);
        fetchUserPoints();
        return;
      } catch (err) {
        console.log("Member API failed, trying Discord auth");
      }
    }
    
    try {
      // Try Discord auth for members
      const response = await apiClient.get(`/api/storefront/${orgPrefix}/members/orders`);
      setIsAuthenticated(true);
      setOrders(Array.isArray(response.data) ? response.data : []);
      fetchUserPoints();
    } catch (err) {
      setIsAuthenticated(false);
      // User can still browse without auth
    }
  }, [orgPrefix, checkMemberSession, fetchUserPoints]);

  const fetchStoreData = useCallback(async () => {
    if (!orgPrefix) {
      setError("Organization not specified");
      setLoading(false);
      return;
    }

    setLoading(true);
    setError(null);
    try {
      // Try member store first, fallback to public store
      let response;
      try {
        response = await apiClient.get(`/api/storefront/${orgPrefix}/members/store`);
      } catch (memberErr) {
        // Fallback to public store data
        response = await apiClient.get(`/api/storefront/${orgPrefix}/store`);
      }
      
      setOrganization(response.data.organization);
      setProducts(response.data.products);
    } catch (err) {
      const errorMessage = `Failed to load store. ${
        err.response?.data?.error || err.response?.data?.message || err.message
      }`;
      setError(errorMessage);
      console.error("Error fetching store data:", err);
    } finally {
      setLoading(false);
    }
  }, [orgPrefix]);

  useEffect(() => {
    // Clear cart when organization changes to ensure session-based cart management
    setCart([]);
    checkAuthentication();
    fetchStoreData();
  }, [checkAuthentication, fetchStoreData]);

  // Load cart from sessionStorage when component mounts
  useEffect(() => {
    const savedCart = sessionStorage.getItem(`cart_${orgPrefix}`);
    if (savedCart) {
      setCart(JSON.parse(savedCart));
    }
  }, [orgPrefix]);

  // Save cart to sessionStorage whenever cart changes
  useEffect(() => {
    if (orgPrefix) {
      sessionStorage.setItem(`cart_${orgPrefix}`, JSON.stringify(cart));
    }
  }, [cart, orgPrefix]);

  const handleLogin = () => {
    // Redirect to member login page
    window.location.href = `/store/${orgPrefix}/login`;
  };

  const handleLogout = () => {
    // Clear member session
    localStorage.removeItem('memberUser');
    localStorage.removeItem('memberOrg');
    sessionStorage.removeItem(`cart_${orgPrefix}`);
    
    // Reset state
    setIsAuthenticated(false);
    setMemberProfile(null);
    setOrders([]);
    setUserPoints(0);
    setCart([]);
    setActiveTab('store');
    
    toast.success("Logged out successfully");
  };

  const addToCart = (product) => {
    setCart(prevCart => {
      const existingItem = prevCart.find(item => item.product.id === product.id);
      if (existingItem) {
        if (existingItem.quantity < product.stock) {
          return prevCart.map(item =>
            item.product.id === product.id
              ? { ...item, quantity: item.quantity + 1 }
              : item
          );
        } else {
          toast.warning(`Only ${product.stock} items available in stock`);
          return prevCart;
        }
      } else {
        return [...prevCart, { product, quantity: 1 }];
      }
    });
    toast.success(`Added ${product.name} to cart`);
  };

  const removeFromCart = (productId) => {
    setCart(prevCart => prevCart.filter(item => item.product.id !== productId));
  };

  const updateQuantity = (productId, newQuantity) => {
    if (newQuantity <= 0) {
      removeFromCart(productId);
      return;
    }

    setCart(prevCart =>
      prevCart.map(item => {
        if (item.product.id === productId) {
          const maxQuantity = item.product.stock;
          const quantity = Math.min(newQuantity, maxQuantity);
          if (quantity !== newQuantity) {
            toast.warning(`Only ${maxQuantity} items available in stock`);
          }
          return { ...item, quantity };
        }
        return item;
      })
    );
  };

  const getTotalPrice = () => {
    return cart.reduce((total, item) => total + (item.product.price * item.quantity), 0);
  };

  const handleCheckout = async () => {
    if (!isAuthenticated) {
      toast.error("Please login to place an order");
      handleLogin();
      return;
    }

    if (cart.length === 0) {
      toast.error("Your cart is empty");
      return;
    }

    setIsProcessingOrder(true);
    try {
      const orderData = {
        total_amount: getTotalPrice(),
        items: cart.map(item => ({
          product_id: item.product.id,
          quantity: item.quantity,
          price: item.product.price
        }))
      };

      // Check if using member session
      const memberUser = localStorage.getItem('memberUser');
      
      if (memberUser) {
        const user = JSON.parse(memberUser);
        await apiClient.post(`/api/storefront/${orgPrefix}/members/orders`, orderData, {
          headers: {
            'X-Member-User-Id': user.id
          }
        });
      } else {
        await apiClient.post(`/api/storefront/${orgPrefix}/members/orders`, orderData);
      }
      
      toast.success("Order placed successfully!");
      setCart([]);
      
      // Refresh data
      checkAuthentication();
      fetchStoreData();
    } catch (err) {
      const errorMessage = `Failed to place order: ${
        err.response?.data?.error || err.response?.data?.message || err.message
      }`;
      toast.error(errorMessage);
      console.error("Error placing order:", err);
    } finally {
      setIsProcessingOrder(false);
    }
  };

  const getStatusColor = (status) => {
    switch (status) {
      case 'pending': return 'bg-yellow-600/50 text-yellow-100 border-yellow-500';
      case 'processing': return 'bg-blue-600/50 text-blue-100 border-blue-500';
      case 'shipped': return 'bg-purple-600/50 text-purple-100 border-purple-500';
      case 'delivered': return 'bg-green-600/50 text-green-100 border-green-500';
      case 'cancelled': return 'bg-red-600/50 text-red-100 border-red-500';
      default: return 'bg-gray-600/50 text-gray-100 border-gray-500';
    }
  };

  if (loading) {
    return (
      <div className="min-h-screen bg-gray-900 flex items-center justify-center">
        <FaSpinner className="animate-spin text-pink-500 text-4xl" />
      </div>
    );
  }

  if (error) {
    return (
      <div className="min-h-screen bg-gray-900 flex items-center justify-center">
        <div className="text-center">
          <h1 className="text-2xl font-bold text-red-500 mb-4">Error</h1>
          <p className="text-gray-400">{error}</p>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-gray-900 text-white">
      {/* Header */}
      <div className="bg-gray-800 border-b border-gray-700">
        <div className="max-w-7xl mx-auto px-4 py-6">
          <div className="flex justify-between items-center">
            <div>
              <h1 className="text-3xl font-bold">{organization?.name} Store</h1>
              <p className="text-gray-400 mt-2">{organization?.description}</p>
            </div>
            <div className="flex items-center space-x-4">
              {isAuthenticated ? (
                <>
                  <div className="flex items-center px-3 py-2 bg-yellow-900/50 border border-yellow-500 rounded-md">
                    <FaCoins className="mr-2 text-yellow-400" />
                    <span className="text-yellow-200">{userPoints} points</span>
                  </div>
                  <div className="flex items-center px-3 py-2 bg-blue-900/50 border border-blue-500 rounded-md">
                    <FaUser className="mr-2 text-blue-400" />
                    <span className="text-blue-200">{memberProfile?.user?.name || 'Member'}</span>
                  </div>
                </>
              ) : (
                <button
                  onClick={handleLogin}
                  className="bg-blue-600 hover:bg-blue-700 px-4 py-2 rounded-md transition-colors flex items-center"
                >
                  <FaUser className="mr-2" />
                  Login
                </button>
              )}
              <button
                onClick={() => setActiveTab('cart')}
                className="relative bg-pink-600 hover:bg-pink-700 px-4 py-2 rounded-md transition-colors flex items-center"
              >
                <FaShoppingCart className="mr-2" />
                Cart ({cart.length})
                {cart.length > 0 && (
                  <span className="absolute -top-2 -right-2 bg-red-500 text-white text-xs rounded-full w-5 h-5 flex items-center justify-center">
                    {cart.reduce((total, item) => total + item.quantity, 0)}
                  </span>
                )}
              </button>
            </div>
          </div>
        </div>
      </div>

      {/* Navigation Tabs */}
      <div className="bg-gray-800 border-b border-gray-700">
        <div className="max-w-7xl mx-auto px-4">
          <nav className="flex space-x-8">
            <button
              onClick={() => setActiveTab('store')}
              className={`py-4 px-2 border-b-2 font-medium text-sm transition-colors ${
                activeTab === 'store'
                  ? 'border-pink-500 text-pink-400'
                  : 'border-transparent text-gray-400 hover:text-gray-300'
              }`}
            >
              <FaStore className="inline mr-2" />
              Store
            </button>
            {isAuthenticated && (
              <>
                <button
                  onClick={() => setActiveTab('dashboard')}
                  className={`py-4 px-2 border-b-2 font-medium text-sm transition-colors ${
                    activeTab === 'dashboard'
                      ? 'border-pink-500 text-pink-400'
                      : 'border-transparent text-gray-400 hover:text-gray-300'
                  }`}
                >
                  <FaTachometerAlt className="inline mr-2" />
                  Dashboard
                </button>
                <button
                  onClick={() => setActiveTab('orders')}
                  className={`py-4 px-2 border-b-2 font-medium text-sm transition-colors ${
                    activeTab === 'orders'
                      ? 'border-pink-500 text-pink-400'
                      : 'border-transparent text-gray-400 hover:text-gray-300'
                  }`}
                >
                  <FaHistory className="inline mr-2" />
                  My Orders ({orders.length})
                </button>
              </>
            )}
            <button
              onClick={() => setActiveTab('cart')}
              className={`py-4 px-2 border-b-2 font-medium text-sm transition-colors ${
                activeTab === 'cart'
                  ? 'border-pink-500 text-pink-400'
                  : 'border-transparent text-gray-400 hover:text-gray-300'
              }`}
            >
              <FaShoppingCart className="inline mr-2" />
              Cart ({cart.length})
            </button>
          </nav>
        </div>
      </div>

      <div className="max-w-7xl mx-auto px-4 py-8">
        {/* Dashboard Tab */}
        {activeTab === 'dashboard' && isAuthenticated && memberProfile && (
          <div>
            <div className="flex justify-between items-center mb-6">
              <h2 className="text-2xl font-bold">Member Dashboard</h2>
              <button
                onClick={handleLogout}
                className="bg-red-600 hover:bg-red-700 px-4 py-2 rounded-md transition-colors flex items-center"
              >
                <FaSignOutAlt className="mr-2" />
                Logout
              </button>
            </div>
            
            <div className="grid grid-cols-1 lg:grid-cols-3 gap-6 mb-8">
              {/* User Info Card */}
              <div className="bg-gray-800 rounded-lg border border-gray-700 p-6">
                <h3 className="text-lg font-semibold mb-4 flex items-center">
                  <FaUser className="mr-2 text-blue-400" />
                  Profile Information
                </h3>
                <div className="space-y-3">
                  <div>
                    <label className="text-sm text-gray-400">Name</label>
                    <p className="text-white">{memberProfile.user.name}</p>
                  </div>
                  <div>
                    <label className="text-sm text-gray-400">Username</label>
                    <p className="text-white">{memberProfile.user.username}</p>
                  </div>
                  {memberProfile.user.email && (
                    <div>
                      <label className="text-sm text-gray-400">Email</label>
                      <p className="text-white">{memberProfile.user.email}</p>
                    </div>
                  )}
                  {memberProfile.user.asu_id && memberProfile.user.asu_id !== 'N/A' && (
                    <div>
                      <label className="text-sm text-gray-400">ASU ID</label>
                      <p className="text-white">{memberProfile.user.asu_id}</p>
                    </div>
                  )}
                  <div>
                    <label className="text-sm text-gray-400">Discord Linked</label>
                    <p className={`${memberProfile.user.discord_linked ? 'text-green-400' : 'text-red-400'}`}>
                      {memberProfile.user.discord_linked ? 'Yes' : 'No'}
                    </p>
                  </div>
                </div>
              </div>
              
              {/* Current Organization Points */}
              <div className="bg-gray-800 rounded-lg border border-gray-700 p-6">
                <h3 className="text-lg font-semibold mb-4 flex items-center">
                  <FaCoins className="mr-2 text-yellow-400" />
                  {memberProfile.current_organization.name} Points
                </h3>
                <div className="text-center">
                  <div className="text-4xl font-bold text-yellow-400 mb-2">
                    {memberProfile.current_organization.points}
                  </div>
                  <p className="text-gray-400">Points in this organization</p>
                </div>
              </div>
              
              {/* Total Points Across All Orgs */}
              <div className="bg-gray-800 rounded-lg border border-gray-700 p-6">
                <h3 className="text-lg font-semibold mb-4 flex items-center">
                  <FaTachometerAlt className="mr-2 text-purple-400" />
                  Total Points
                </h3>
                <div className="text-center">
                  <div className="text-4xl font-bold text-purple-400 mb-2">
                    {memberProfile.total_points_all_orgs}
                  </div>
                  <p className="text-gray-400">Points across all organizations</p>
                </div>
              </div>
            </div>
            
            {/* Organization Memberships */}
            <div className="bg-gray-800 rounded-lg border border-gray-700 p-6">
              <h3 className="text-lg font-semibold mb-4">Organization Memberships</h3>
              <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
                {memberProfile.organizations.map((org) => (
                  <div 
                    key={org.id} 
                    className={`p-4 rounded-lg border ${
                      org.is_current 
                        ? 'border-pink-500 bg-pink-900/20' 
                        : 'border-gray-600 bg-gray-700'
                    }`}
                  >
                    <div className="flex justify-between items-start mb-2">
                      <h4 className="font-semibold text-white">{org.name}</h4>
                      {org.is_current && (
                        <span className="bg-pink-500 text-white text-xs px-2 py-1 rounded">
                          Current
                        </span>
                      )}
                    </div>
                    <p className="text-sm text-gray-400 mb-2">{org.description}</p>
                    <div className="flex justify-between items-center">
                      <span className="text-sm text-gray-400">Points:</span>
                      <span className="font-semibold text-yellow-400">{org.points}</span>
                    </div>
                    {!org.is_current && (
                      <button
                        onClick={() => window.location.href = `/store/${org.prefix}`}
                        className="w-full mt-2 bg-blue-600 hover:bg-blue-700 text-white text-xs py-1 rounded transition-colors"
                      >
                        Visit Store
                      </button>
                    )}
                  </div>
                ))}
              </div>
            </div>
          </div>
        )}

        {/* Store Tab */}
        {activeTab === 'store' && (
          <div>
            <h2 className="text-2xl font-bold mb-6">Available Products</h2>
            {products.length === 0 ? (
              <div className="text-center py-12">
                <p className="text-gray-400 text-lg">No products available at the moment.</p>
              </div>
            ) : (
              <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
                {products.map((product) => (
                  <div key={product.id} className="bg-gray-800 rounded-lg border border-gray-700 p-6">
                    {product.image_url && (
                      <img
                        src={product.image_url}
                        alt={product.name}
                        className="w-full h-48 object-cover rounded-md mb-4"
                      />
                    )}
                    <h3 className="text-xl font-semibold mb-2">{product.name}</h3>
                    {product.description && (
                      <p className="text-gray-400 mb-4">{product.description}</p>
                    )}
                    <div className="flex justify-between items-center mb-4">
                      <span className="text-2xl font-bold text-green-400">
                        {product.price.toFixed(2)}
                      </span>
                      <span className="text-sm text-gray-400">
                        {product.stock} in stock
                      </span>
                    </div>
                    <button
                      onClick={() => addToCart(product)}
                      disabled={product.stock === 0}
                      className="w-full bg-pink-600 hover:bg-pink-700 disabled:bg-gray-600 disabled:cursor-not-allowed px-4 py-2 rounded-md transition-colors flex items-center justify-center"
                    >
                      <FaShoppingCart className="mr-2" />
                      {product.stock === 0 ? "Out of Stock" : "Add to Cart"}
                    </button>
                  </div>
                ))}
              </div>
            )}
          </div>
        )}

        {/* Orders Tab */}
        {activeTab === 'orders' && (
          <div>
            {!isAuthenticated ? (
              <div className="text-center py-12">
                <FaUser className="mx-auto text-gray-500 text-6xl mb-4" />
                <h3 className="text-xl font-semibold mb-2 text-gray-300">Login Required</h3>
                <p className="text-gray-400 mb-6">Please login to view your orders</p>
                <button
                  onClick={handleLogin}
                  className="bg-blue-600 hover:bg-blue-700 px-6 py-2 rounded-md transition-colors"
                >
                  Login to View Orders
                </button>
              </div>
            ) : (
              <div>
                <h2 className="text-2xl font-bold mb-6">My Orders ({orders.length})</h2>
                {orders.length === 0 ? (
                  <div className="text-center py-12">
                    <FaHistory className="mx-auto text-gray-500 text-6xl mb-4" />
                    <h3 className="text-xl font-semibold mb-2 text-gray-300">No Orders Yet</h3>
                    <p className="text-gray-400 mb-6">You haven't placed any orders yet.</p>
                    <button
                      onClick={() => setActiveTab('store')}
                      className="bg-green-600 hover:bg-green-700 px-6 py-2 rounded-md transition-colors"
                    >
                      Browse Store
                    </button>
                  </div>
                ) : (
                  <div className="space-y-4">
                    {orders.map((order) => (
                      <div key={order.id} className="bg-gray-800 rounded-lg border border-gray-700 p-6">
                        <div className="flex justify-between items-start mb-4">
                          <div>
                            <h3 className="text-lg font-semibold">Order #{order.id}</h3>
                            <p className="text-gray-400 text-sm">
                              {new Date(order.created_at).toLocaleDateString()}
                            </p>
                          </div>
                          <div className="text-right">
                            <div className={`px-3 py-1 rounded-full text-xs font-semibold border ${getStatusColor(order.status)}`}>
                              {order.status.charAt(0).toUpperCase() + order.status.slice(1)}
                            </div>
                            <p className="text-lg font-bold text-green-400 mt-2">
                              {order.total_amount.toFixed(2)}
                            </p>
                          </div>
                        </div>
                        {order.items && order.items.length > 0 && (
                          <div className="border-t border-gray-700 pt-4">
                            <h4 className="font-medium mb-2">Items:</h4>
                            <div className="space-y-2 mb-4">
                              {order.items.map((item, index) => (
                                <div key={index} className="flex justify-between text-sm">
                                  <span>{item.product_name || `Product #${item.product_id}`}</span>
                                  <span>{item.quantity} × {item.price_at_time.toFixed(2)}</span>
                                </div>
                              ))}
                            </div>
                            {order.message && (
                              <div className="bg-blue-900/30 border border-blue-500/50 rounded-md p-3">
                                <h5 className="font-medium text-blue-300 mb-1 flex items-center">
                                  <FaEnvelope className="mr-2" />
                                  Pickup Instructions
                                </h5>
                                <p className="text-blue-100 text-sm">{order.message}</p>
                              </div>
                            )}
                          </div>
                        )}
                      </div>
                    ))}
                  </div>
                )}
              </div>
            )}
          </div>
        )}

        {/* Cart Tab */}
        {activeTab === 'cart' && (
          <div>
            <h2 className="text-2xl font-bold mb-6">Shopping Cart</h2>
            {cart.length === 0 ? (
              <div className="text-center py-12">
                <FaShoppingCart className="mx-auto text-gray-500 text-6xl mb-4" />
                <h3 className="text-xl font-semibold mb-2 text-gray-300">Your Cart is Empty</h3>
                <p className="text-gray-400 mb-6">Add some items to get started!</p>
                <button
                  onClick={() => setActiveTab('store')}
                  className="bg-green-600 hover:bg-green-700 px-6 py-2 rounded-md transition-colors"
                >
                  Browse Store
                </button>
              </div>
            ) : (
              <div className="max-w-2xl mx-auto">
                <div className="space-y-4 mb-6">
                  {cart.map((item) => (
                    <div key={item.product.id} className="bg-gray-800 rounded-lg border border-gray-700 p-4">
                      <div className="flex items-center justify-between">
                        <div className="flex-1">
                          <h4 className="font-semibold">{item.product.name}</h4>
                          <p className="text-sm text-gray-400">
                            {item.product.price.toFixed(2)} each
                          </p>
                        </div>
                        <div className="flex items-center space-x-2">
                          <button
                            onClick={() => updateQuantity(item.product.id, item.quantity - 1)}
                            className="bg-gray-700 hover:bg-gray-600 p-1 rounded"
                          >
                            <FaMinus className="text-xs" />
                          </button>
                          <span className="w-8 text-center">{item.quantity}</span>
                          <button
                            onClick={() => updateQuantity(item.product.id, item.quantity + 1)}
                            className="bg-gray-700 hover:bg-gray-600 p-1 rounded"
                          >
                            <FaPlus className="text-xs" />
                          </button>
                          <button
                            onClick={() => removeFromCart(item.product.id)}
                            className="bg-red-600 hover:bg-red-700 px-2 py-1 rounded text-xs ml-2"
                          >
                            Remove
                          </button>
                        </div>
                      </div>
                      <div className="text-right mt-2">
                        <span className="font-semibold">
                          {(item.quantity * item.product.price).toFixed(2)}
                        </span>
                      </div>
                    </div>
                  ))}
                </div>

                <div className="bg-gray-800 rounded-lg border border-gray-700 p-6">
                  <div className="flex justify-between items-center text-xl font-bold mb-4">
                    <span>Total:</span>
                    <span className="text-green-400">{getTotalPrice().toFixed(2)}</span>
                  </div>

                  {!isAuthenticated && (
                    <div className="mb-4 p-4 bg-blue-900/50 border border-blue-500 rounded-md">
                      <p className="text-blue-200 text-sm">
                        <FaUser className="inline mr-2" />
                        Please login to place your order
                      </p>
                    </div>
                  )}

                  <button
                    onClick={isAuthenticated ? handleCheckout : handleLogin}
                    disabled={isProcessingOrder || cart.length === 0}
                    className="w-full bg-green-600 hover:bg-green-700 disabled:bg-gray-600 disabled:cursor-not-allowed px-4 py-3 rounded-md transition-colors flex items-center justify-center font-semibold"
                  >
                    {isProcessingOrder ? (
                      <FaSpinner className="animate-spin mr-2" />
                    ) : (
                      <FaCheck className="mr-2" />
                    )}
                    {isProcessingOrder 
                      ? "Processing..." 
                      : isAuthenticated 
                        ? "Place Order" 
                        : "Login to Order"
                    }
                  </button>
                </div>
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  );
};

export default MemberStorePage;