import React, { useState, useEffect, useCallback } from "react";
import apiClient from "../components/utils/axios";
import OrganizationNavbar from "../components/shared/OrganizationNavbar";
import { FaReceipt, FaPlus, FaTimes, FaSpinner, FaTrash } from "react-icons/fa";
import { toast } from "react-toastify";
import { useAuth } from "../components/auth/AuthContext";

const TransactionsPage = () => {
  const { currentOrg } = useAuth();
  const [transactions, setTransactions] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  const [showAddForm, setShowAddForm] = useState(false);
  const [newOrderData, setNewOrderData] = useState({
    user_id: "",
    total_amount: "",
    items: [{ product_id: "", quantity: "", price: "" }],
  });
  const [addTransactionLoading, setAddTransactionLoading] = useState(false);
  const [addTransactionError, setAddTransactionError] = useState(null);

  const fetchTransactions = useCallback(async () => {
    if (!currentOrg?.prefix) {
      setError("No organization selected");
      setLoading(false);
      return;
    }

    setLoading(true);
    setError(null);
    try {
      const response = await apiClient.get(`/api/merch/${currentOrg.prefix}/orders`);
      setTransactions(Array.isArray(response.data) ? response.data : []);
    } catch (err) {
      const errorMessage = `Failed to fetch transactions. ${
        err.response?.data?.message || err.message
      }`;
      setError(errorMessage);
      toast.error(errorMessage);
      console.error("Error fetching transactions:", err.response || err);
    } finally {
      setLoading(false);
    }
  }, [currentOrg?.prefix]);

  useEffect(() => {
    fetchTransactions();
  }, [fetchTransactions]);

  const handleNewOrderChange = (e) => {
    const { name, value } = e.target;
    setNewOrderData((prevData) => ({
      ...prevData,
      [name]: Number(value),
    }));
  };

  const handleItemChange = (index, e) => {
    const { name, value } = e.target;
    const updatedItems = newOrderData.items.map((item, i) =>
      i === index ? { ...item, [name]: Number(value) } : item
    );
    setNewOrderData((prevData) => ({
      ...prevData,
      items: updatedItems,
    }));
  };

  const handleAddItem = () => {
    setNewOrderData((prevData) => ({
      ...prevData,
      items: [...prevData.items, { product_id: "", quantity: "", price: "" }],
    }));
  };

  const handleRemoveItem = (index) => {
    const updatedItems = newOrderData.items.filter((_, i) => i !== index);
    setNewOrderData((prevData) => ({
      ...prevData,
      items: updatedItems,
    }));
  };

  const handleAddTransactionSubmit = async (e) => {
    e.preventDefault();
    
    if (!currentOrg?.prefix) {
      toast.error("No organization selected");
      return;
    }
    
    setAddTransactionLoading(true);
    setAddTransactionError(null);

    const validItems = newOrderData.items.filter(
      (item) => item.product_id && item.quantity && item.price
    );

    if (validItems.length === 0) {
      const errorMessage = "Please add at least one valid item.";
      setAddTransactionError(errorMessage);
      toast.error(errorMessage);
      setAddTransactionLoading(false);
      return;
    }

    const payload = {
      user_id: newOrderData.user_id,
      total_amount: newOrderData.total_amount,
      items: validItems,
    };

    try {
      await apiClient.post(`/api/merch/${currentOrg.prefix}/orders`, payload);
      toast.success("Transaction added successfully!");
      setShowAddForm(false);
      setNewOrderData({
        user_id: "",
        total_amount: "",
        items: [{ product_id: "", quantity: "", price: "" }],
      });
      fetchTransactions();
    } catch (err) {
      const errorMessage = `Failed to add transaction: ${
        err.response?.data?.message || err.message
      }`;
      setAddTransactionError(errorMessage);
      toast.error(errorMessage);
      console.error("Error adding transaction:", err.response || err);
    } finally {
      setAddTransactionLoading(false);
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
      <div className="max-w-6xl mx-auto">
        <div className="text-center mb-8">
          <h1 className="text-3xl font-bold mb-2">Transactions</h1>
          <p className="text-gray-400">
            Manage all merchandise orders and transactions for {currentOrg.name}
          </p>
        </div>

        {error && (
          <div className="mb-6 p-4 bg-red-900/50 border border-red-500 rounded-md text-red-200">
            {error}
          </div>
        )}

        <div className="bg-gray-900/50 backdrop-blur-sm rounded-xl border border-gray-700 p-6 mb-8">
          <div className="flex items-center justify-between mb-4">
            <h2 className="text-xl font-semibold flex items-center text-white">
              <FaReceipt className="mr-2 text-pink-400" />
              Recent Orders
            </h2>
            <button
              onClick={() => setShowAddForm(!showAddForm)}
              className="px-4 py-2 bg-green-600 hover:bg-green-700 text-white rounded-md transition-colors flex items-center"
            >
              {showAddForm ? (
                <FaTimes className="mr-2" />
              ) : (
                <FaPlus className="mr-2" />
              )}
              {showAddForm ? "Hide Form" : "Add New Transaction"}
            </button>
          </div>

          {loading ? (
            <div className="flex items-center justify-center py-12">
              <FaSpinner className="animate-spin text-pink-500 text-4xl" />
            </div>
          ) : transactions.length === 0 ? (
            <div className="text-center py-8 text-gray-400">
              No transactions found.
            </div>
          ) : (
            <div className="overflow-x-auto">
              <table className="min-w-full border-collapse">
                <thead className="text-gray-300 border-b border-gray-700">
                  <tr>
                    <th className="p-3 text-left font-medium">Order ID</th>
                    <th className="p-3 text-left font-medium">User ID</th>
                    <th className="p-3 text-left font-medium">Status</th>
                    <th className="p-3 text-left font-medium">Date</th>
                    <th className="p-3 text-right font-medium">Total Cost</th>
                  </tr>
                </thead>
                <tbody>
                  {transactions.map((transaction) => (
                    <tr
                      key={transaction.id}
                      className="border-b border-gray-800 last:border-b-0"
                    >
                      <td className="p-3">{transaction.id}</td>
                      <td className="p-3">{transaction.user_id}</td>
                      <td className="p-3">
                        <span
                          className={`px-2 py-1 rounded text-xs font-semibold ${
                            transaction.status === "pending"
                              ? "bg-yellow-600/50 text-yellow-100"
                              : "bg-green-600/50 text-green-100"
                          }`}
                        >
                          {transaction.status}
                        </span>
                      </td>
                      <td className="p-3 text-gray-400">
                        {new Date(transaction.created_at).toLocaleDateString()}
                      </td>
                      <td className="p-3 text-right font-bold text-white">
                        ${transaction.total_amount.toFixed(2)}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>

        {/* Add Transaction Form */}
        {showAddForm && (
          <div className="bg-gray-900/50 backdrop-blur-sm rounded-xl border border-gray-700 p-6 mt-8 max-w-2xl mx-auto">
            <h2 className="text-2xl font-bold mb-4 text-white text-center">
              Add New Order
            </h2>
            {addTransactionError && (
              <p className="text-red-500 text-center mb-4">
                {addTransactionError}
              </p>
            )}
            <form onSubmit={handleAddTransactionSubmit} className="space-y-4">
              <div>
                <label
                  htmlFor="user_id"
                  className="block text-sm font-medium text-gray-300 mb-1"
                >
                  User ID:
                </label>
                <input
                  type="number"
                  id="user_id"
                  name="user_id"
                  value={newOrderData.user_id}
                  onChange={handleNewOrderChange}
                  className="w-full px-3 py-2 bg-gray-800 border border-gray-600 rounded-md text-white placeholder-gray-400 focus:outline-none focus:border-green-500"
                  placeholder="e.g., 1 (must be an existing user ID)"
                  required
                />
              </div>
              <div>
                <label
                  htmlFor="total_amount"
                  className="block text-sm font-medium text-gray-300 mb-1"
                >
                  Total Amount:
                </label>
                <input
                  type="number"
                  id="total_amount"
                  name="total_amount"
                  value={newOrderData.total_amount}
                  onChange={handleNewOrderChange}
                  className="w-full px-3 py-2 bg-gray-800 border border-gray-600 rounded-md text-white placeholder-gray-400 focus:outline-none focus:border-green-500"
                  step="0.01"
                  placeholder="e.g., 150.75"
                  required
                />
              </div>

              <h3 className="text-lg font-semibold mt-6 mb-3 text-gray-200">
                Order Items:
              </h3>
              {newOrderData.items.map((item, index) => (
                <div key={index} className="flex space-x-2 items-end">
                  <div className="flex-1">
                    <label
                      htmlFor={`product_id-${index}`}
                      className="block text-gray-400 text-xs font-bold mb-1"
                    >
                      Product ID:
                    </label>
                    <input
                      type="number"
                      id={`product_id-${index}`}
                      name="product_id"
                      value={item.product_id}
                      onChange={(e) => handleItemChange(index, e)}
                      className="w-full px-3 py-2 bg-gray-800 border border-gray-600 rounded-md text-white placeholder-gray-400 text-sm focus:outline-none focus:border-green-500"
                      placeholder="e.g., 101"
                      required
                    />
                  </div>
                  <div className="flex-1">
                    <label
                      htmlFor={`quantity-${index}`}
                      className="block text-gray-400 text-xs font-bold mb-1"
                    >
                      Quantity:
                    </label>
                    <input
                      type="number"
                      id={`quantity-${index}`}
                      name="quantity"
                      value={item.quantity}
                      onChange={(e) => handleItemChange(index, e)}
                      className="w-full px-3 py-2 bg-gray-800 border border-gray-600 rounded-md text-white placeholder-gray-400 text-sm focus:outline-none focus:border-green-500"
                      placeholder="e.g., 2"
                      required
                    />
                  </div>
                  <div className="flex-1">
                    <label
                      htmlFor={`price-${index}`}
                      className="block text-gray-400 text-xs font-bold mb-1"
                    >
                      Price:
                    </label>
                    <input
                      type="number"
                      id={`price-${index}`}
                      name="price"
                      value={item.price}
                      onChange={(e) => handleItemChange(index, e)}
                      className="w-full px-3 py-2 bg-gray-800 border border-gray-600 rounded-md text-white placeholder-gray-400 text-sm focus:outline-none focus:border-green-500"
                      step="0.01"
                      placeholder="e.g., 50.00"
                      required
                    />
                  </div>
                  {newOrderData.items.length > 1 && (
                    <button
                      type="button"
                      onClick={() => handleRemoveItem(index)}
                      className="bg-red-600 hover:bg-red-700 text-white p-2 rounded-md transition-colors"
                      title="Remove Item"
                    >
                      <FaTrash />
                    </button>
                  )}
                </div>
              ))}
              <div className="flex justify-between items-center">
                <button
                  type="button"
                  onClick={handleAddItem}
                  className="px-4 py-2 bg-blue-600 hover:bg-blue-700 text-white font-bold rounded-md transition-colors mt-2"
                >
                  Add Another Item
                </button>
                <div className="flex space-x-4 mt-2">
                  <button
                    type="submit"
                    className="px-6 py-2 bg-purple-600 hover:bg-purple-700 text-white font-bold rounded-md transition-colors flex items-center justify-center"
                    disabled={addTransactionLoading}
                  >
                    {addTransactionLoading && (
                      <FaSpinner className="animate-spin mr-2" />
                    )}
                    Submit Order
                  </button>
                  <button
                    type="button"
                    onClick={() => setShowAddForm(false)}
                    className="px-6 py-2 bg-gray-600 hover:bg-gray-700 text-white font-bold rounded-md transition-colors"
                  >
                    Cancel
                  </button>
                </div>
              </div>
            </form>
          </div>
        )}
      </div>
    </OrganizationNavbar>
  );
};

export default TransactionsPage;
