import { useState, useEffect, useCallback, type ChangeEvent, type FormEvent } from "react";
import { useParams } from "react-router-dom";
import axios from "axios";
import apiClient from "../components/utils/axios";
import OrganizationNavbar from "../components/shared/OrganizationNavbar";
import { FaReceipt, FaPlus, FaTimes, FaSpinner, FaTrash, FaEdit, FaEnvelope } from "react-icons/fa";
import { toast } from "react-toastify";
import { useAuth } from "../components/auth/AuthContext";
import type { ApiError } from "../types";

// One item of an order in GET /api/storefront/<org_prefix>/orders.
interface OrderItem {
  id: number;
  product_id: number;
  quantity: number;
  price_at_time: number;
}

// One order in GET /api/storefront/<org_prefix>/orders.
interface Transaction {
  id: number;
  user_id: number;
  total_amount: number;
  status: string;
  message: string | null;
  created_at: string;
  updated_at: string | null;
  organization_id: number;
  user_name: string | null;
  user_email: string | null;
  items: OrderItem[];
}

// The add form keeps "" in a field until the officer types a number.
interface NewOrderItem {
  product_id: number | "";
  quantity: number | "";
  price: number | "";
}

interface NewOrderData {
  user_id: number | "";
  total_amount: number | "";
  items: NewOrderItem[];
}

// The error text of a failed request: the API error, else the error message.
const errorDetail = (err: unknown) => {
  if (axios.isAxiosError<ApiError>(err)) {
    return err.response?.data?.error || err.response?.data?.message || err.message;
  }
  return err instanceof Error ? err.message : String(err);
};

const TransactionsPage = () => {
  const { orgPrefix } = useParams();
  const { currentOrg } = useAuth();
  const [transactions, setTransactions] = useState<Transaction[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const [showAddForm, setShowAddForm] = useState(false);
  const [newOrderData, setNewOrderData] = useState<NewOrderData>({
    user_id: "",
    total_amount: "",
    items: [{ product_id: "", quantity: "", price: "" }],
  });
  const [addTransactionLoading, setAddTransactionLoading] = useState(false);
  const [addTransactionError, setAddTransactionError] = useState<string | null>(null);
  
  // Message management state
  const [editingMessage, setEditingMessage] = useState<number | null>(null);
  const [messageText, setMessageText] = useState('');
  const [messageLoading, setMessageLoading] = useState(false);

  const fetchTransactions = useCallback(async () => {
    const prefixToUse = orgPrefix || currentOrg?.prefix;
    if (!prefixToUse) {
      setError("No organization selected");
      setLoading(false);
      return;
    }

    setLoading(true);
    setError(null);
    try {
      const response = await apiClient.get<Transaction[]>(`/api/storefront/${prefixToUse}/orders`);
      setTransactions(Array.isArray(response.data) ? response.data : []);
    } catch (err) {
      const errorMessage = `Failed to fetch transactions. ${errorDetail(err)}`;
      setError(errorMessage);
      toast.error(errorMessage);
      console.error("Error fetching transactions:", (axios.isAxiosError(err) && err.response) || err);
    } finally {
      setLoading(false);
    }
  }, [orgPrefix, currentOrg?.prefix]);

  useEffect(() => {
    fetchTransactions();
  }, [fetchTransactions]);

  const handleNewOrderChange = (e: ChangeEvent<HTMLInputElement>) => {
    const { name, value } = e.target;
    setNewOrderData((prevData) => ({
      ...prevData,
      [name]: Number(value),
    }));
  };

  const handleItemChange = (index: number, e: ChangeEvent<HTMLInputElement>) => {
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

  const handleRemoveItem = (index: number) => {
    const updatedItems = newOrderData.items.filter((_, i) => i !== index);
    setNewOrderData((prevData) => ({
      ...prevData,
      items: updatedItems,
    }));
  };

  const handleAddTransactionSubmit = async (e: FormEvent<HTMLFormElement>) => {
    e.preventDefault();
    
    const prefixToUse = orgPrefix || currentOrg?.prefix;
    if (!prefixToUse) {
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
      await apiClient.post(`/api/storefront/${prefixToUse}/orders`, payload);
      toast.success("Transaction added successfully!");
      setShowAddForm(false);
      setNewOrderData({
        user_id: "",
        total_amount: "",
        items: [{ product_id: "", quantity: "", price: "" }],
      });
      fetchTransactions();
    } catch (err) {
      const errorMessage = `Failed to add transaction: ${errorDetail(err)}`;
      setAddTransactionError(errorMessage);
      toast.error(errorMessage);
      console.error("Error adding transaction:", (axios.isAxiosError(err) && err.response) || err);
    } finally {
      setAddTransactionLoading(false);
    }
  };

  const handleEditMessage = (transaction: Transaction) => {
    setEditingMessage(transaction.id);
    setMessageText(transaction.message || '');
  };

  const handleSaveMessage = async (transactionId: number) => {
    const prefixToUse = orgPrefix || currentOrg?.prefix;
    if (!prefixToUse) {
      toast.error("No organization selected");
      return;
    }

    setMessageLoading(true);
    try {
      await apiClient.put(`/api/storefront/${prefixToUse}/orders/${transactionId}`, {
        message: messageText
      });
      toast.success("Message updated successfully!");
      setEditingMessage(null);
      setMessageText('');
      fetchTransactions();
    } catch (err) {
      const errorMessage = `Failed to update message: ${errorDetail(err)}`;
      toast.error(errorMessage);
    } finally {
      setMessageLoading(false);
    }
  };

  const handleCancelMessage = () => {
    setEditingMessage(null);
    setMessageText('');
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
            Manage all storefront orders and transactions for {currentOrg?.name || 'the organization'}
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
                    <th className="p-3 text-left font-medium">Customer</th>
                    <th className="p-3 text-left font-medium">Status</th>
                    <th className="p-3 text-left font-medium">Message</th>
                    <th className="p-3 text-left font-medium">Date</th>
                    <th className="p-3 text-right font-medium">Total Cost</th>
                    <th className="p-3 text-center font-medium">Actions</th>
                  </tr>
                </thead>
                <tbody>
                  {transactions.map((transaction) => (
                    <tr
                      key={transaction.id}
                      className="border-b border-gray-800 last:border-b-0"
                    >
                      <td className="p-3">#{transaction.id}</td>
                      <td className="p-3">
                        <div>
                          <div className="font-medium text-white">
                            {transaction.user_name || `User ${transaction.user_id}`}
                          </div>
                          {transaction.user_email && (
                            <div className="text-xs text-gray-400">
                              {transaction.user_email}
                            </div>
                          )}
                          <div className="text-xs text-gray-500">
                            ID: {transaction.user_id}
                          </div>
                        </div>
                      </td>
                      <td className="p-3">
                        <span
                          className={`px-2 py-1 rounded text-xs font-semibold ${
                            transaction.status === "pending"
                              ? "bg-yellow-600/50 text-yellow-100"
                              : transaction.status === "processing"
                              ? "bg-blue-600/50 text-blue-100"
                              : transaction.status === "shipped"
                              ? "bg-purple-600/50 text-purple-100"
                              : transaction.status === "delivered"
                              ? "bg-green-600/50 text-green-100"
                              : "bg-red-600/50 text-red-100"
                          }`}
                        >
                          {transaction.status.charAt(0).toUpperCase() + transaction.status.slice(1)}
                        </span>
                      </td>
                      <td className="p-3">
                        {editingMessage === transaction.id ? (
                          <div className="flex items-center space-x-2">
                            <input
                              type="text"
                              value={messageText}
                              onChange={(e) => setMessageText(e.target.value)}
                              className="flex-1 px-2 py-1 bg-gray-700 border border-gray-600 rounded text-sm text-white"
                              placeholder="Pickup instructions..."
                            />
                            <button
                              onClick={() => handleSaveMessage(transaction.id)}
                              disabled={messageLoading}
                              className="bg-green-600 hover:bg-green-700 px-2 py-1 rounded text-xs"
                            >
                              {messageLoading ? <FaSpinner className="animate-spin" /> : "Save"}
                            </button>
                            <button
                              onClick={handleCancelMessage}
                              className="bg-gray-600 hover:bg-gray-700 px-2 py-1 rounded text-xs"
                            >
                              Cancel
                            </button>
                          </div>
                        ) : (
                          <div className="flex items-center space-x-2">
                            <span className="text-sm text-gray-300 flex-1">
                              {transaction.message || "No message"}
                            </span>
                            <button
                              onClick={() => handleEditMessage(transaction)}
                              className="text-blue-400 hover:text-blue-300"
                              title="Edit pickup message"
                            >
                              <FaEdit className="text-xs" />
                            </button>
                          </div>
                        )}
                      </td>
                      <td className="p-3 text-gray-400 text-sm">
                        {new Date(transaction.created_at).toLocaleDateString()}
                      </td>
                      <td className="p-3 text-right font-bold text-white">
                        {transaction.total_amount.toFixed(2)}
                      </td>
                      <td className="p-3 text-center">
                        <button
                          onClick={() => handleEditMessage(transaction)}
                          className="bg-blue-600 hover:bg-blue-700 px-3 py-1 rounded text-xs transition-colors"
                          title="Add pickup instructions"
                        >
                          <FaEnvelope className="mr-1" />
                          Message
                        </button>
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
