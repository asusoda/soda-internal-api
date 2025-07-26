// import React, { useState, useEffect, useCallback } from "react";
// import Sidebar from "../components/SideBar";
// import apiClient from "../components/utils/axios"; // Assuming axios instance is here

// const TransactionsPage = () => {
//   const [isSidebarOpen, setIsSidebarOpen] = useState(false);
//   const [transactions, setTransactions] = useState([]);
//   const [loading, setLoading] = useState(true);
//   const [error, setError] = useState(null);
//   const [filter, setFilter] = useState("Last 30 days"); // State for the filter dropdown

//   // Function to fetch transactions from the API
//   const fetchTransactions = useCallback(async () => {
//     setLoading(true);
//     setError(null); // Clear previous errors
//     try {
//       // Correct endpoint for your Flask API
//       const response = await apiClient.get("/merch/orders");

//       // Robustly ensure transactions is an array
//       setTransactions(Array.isArray(response.data) ? response.data : []);
//     } catch (err) {
//       // Improved error message for debugging
//       setError(
//         "Failed to fetch transactions. " +
//           (err.response?.data?.error ||
//             err.response?.data?.message ||
//             err.message)
//       );
//       console.error("Error fetching transactions:", err.response || err);
//     } finally {
//       setLoading(false);
//     }
//   }, []); // Empty dependency array means this function is created once

//   // Fetch transactions on component mount
//   useEffect(() => {
//     fetchTransactions();
//   }, [fetchTransactions]); // Re-run if fetchTransactions changes (due to useCallback, it won't often)

//   // Handle filter change (you'd implement filtering logic here or in backend)
//   const handleFilterChange = (event) => {
//     setFilter(event.target.value);
//     // If you ever want to filter on the frontend, you'd do it here
//     // based on the 'transactions' state or by re-fetching with parameters.
//   };

//   if (loading) {
//     return (
//       <div className="min-h-screen flex bg-gray-900 text-white justify-center items-center">
//         Loading transactions...
//       </div>
//     );
//   }

//   if (error) {
//     return (
//       <div className="min-h-screen flex bg-gray-900 text-white justify-center items-center text-red-500">
//         Error: {error}
//       </div>
//     );
//   }

//   return (
//     <div className="min-h-screen flex bg-gray-900 text-white">
//       <Sidebar
//         isSidebarOpen={isSidebarOpen}
//         toggleSidebar={() => setIsSidebarOpen(!isSidebarOpen)}
//       />
//       <div
//         className={`flex-1 p-8 transition-all duration-300 ${
//           isSidebarOpen ? "ml-60" : "ml-16"
//         }`}
//       >
//         <div className="flex items-center justify-between mb-6">
//           <h1 className="text-4xl font-bold text-[#ba3554]">Transactions</h1>
//           <select
//             className="bg-gray-800 text-white border border-gray-600 rounded p-2"
//             value={filter}
//             onChange={handleFilterChange}
//           >
//             <option>Last 30 days</option>
//             <option>Last 7 days</option>
//             <option>Last 90 days</option>
//             <option>All time</option> {/* Added an "All time" option */}
//           </select>
//         </div>
//         <div className="overflow-x-auto">
//           {transactions.length > 0 ? (
//             <table className="w-full border-collapse bg-gray-800 rounded-xl overflow-hidden shadow-md">
//               <thead className="bg-gray-700 text-white">
//                 <tr>
//                   {/* Removed Name, Email, ASU ID, Item Bought */}
//                   <th className="p-3 text-left">Order ID</th>
//                   <th className="p-3 text-left">User ID</th>{" "}
//                   {/* Displaying the raw user_id string */}
//                   <th className="p-3 text-left">Status</th>
//                   <th className="p-3 text-left">Date</th>
//                   <th className="p-3 text-right">Total Cost</th>
//                 </tr>
//               </thead>
//               <tbody>
//                 {transactions.map((transaction) => (
//                   <tr
//                     key={transaction.id}
//                     className="bg-gray-600 hover:bg-gray-500 transition-colors"
//                   >
//                     <td className="p-3">{transaction.id}</td>
//                     <td className="p-3">{transaction.user_id}</td>{" "}
//                     {/* Displaying user_id */}
//                     <td className="p-3">{transaction.status}</td>
//                     <td className="p-3">
//                       {new Date(transaction.created_at).toLocaleDateString()}{" "}
//                       {/* Using created_at */}
//                     </td>
//                     <td className="p-3 text-right">
//                       ${transaction.total_amount.toFixed(2)}{" "}
//                       {/* Using total_amount */}
//                     </td>
//                   </tr>
//                 ))}
//               </tbody>
//             </table>
//           ) : (
//             <div className="text-center py-8 text-gray-400">
//               No transactions found for the selected period.
//             </div>
//           )}
//         </div>
//       </div>
//     </div>
//   );
// };

// export default TransactionsPage;
import React, { useState, useEffect, useCallback } from "react";
import Sidebar from "../components/SideBar";
import apiClient from "../components/utils/axios"; // Assuming axios instance is here

const TransactionsPage = () => {
  const [isSidebarOpen, setIsSidebarOpen] = useState(false);
  const [transactions, setTransactions] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [filter, setFilter] = useState("Last 30 days");

  // State for the new transaction form
  const [showAddForm, setShowAddForm] = useState(false);
  const [newOrderData, setNewOrderData] = useState({
    user_id: "",
    total_amount: "",
    items: [{ product_id: "", quantity: "", price: "" }],
  });
  const [addTransactionLoading, setAddTransactionLoading] = useState(false);
  const [addTransactionError, setAddTransactionError] = useState(null);

  // Function to fetch transactions from the API
  const fetchTransactions = useCallback(async () => {
    setLoading(true);
    setError(null); // Clear previous errors
    try {
      const response = await apiClient.get("/merch/orders"); // Your Flask endpoint
      setTransactions(Array.isArray(response.data) ? response.data : []);
    } catch (err) {
      setError(
        "Failed to fetch transactions. " +
          (err.response?.data?.error ||
            err.response?.data?.message ||
            err.message)
      );
      console.error("Error fetching transactions:", err.response || err);
    } finally {
      setLoading(false);
    }
  }, []);

  // Fetch transactions on component mount
  useEffect(() => {
    fetchTransactions();
  }, [fetchTransactions]);

  // Handle filter change (for future filtering logic)
  const handleFilterChange = (event) => {
    setFilter(event.target.value);
  };

  // Handle changes in the new order form
  const handleNewOrderChange = (e) => {
    const { name, value } = e.target;
    setNewOrderData((prevData) => ({
      ...prevData,
      [name]:
        name === "user_id" || name === "total_amount" ? Number(value) : value,
    }));
  };

  // Handle changes in individual order items
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

  // Add a new item row to the form
  const handleAddItem = () => {
    setNewOrderData((prevData) => ({
      ...prevData,
      items: [...prevData.items, { product_id: "", quantity: "", price: "" }],
    }));
  };

  // Remove an item row from the form
  const handleRemoveItem = (index) => {
    const updatedItems = newOrderData.items.filter((_, i) => i !== index);
    setNewOrderData((prevData) => ({
      ...prevData,
      items: updatedItems,
    }));
  };

  // Handle submission of the new transaction form
  const handleAddTransactionSubmit = async (e) => {
    e.preventDefault();
    setAddTransactionLoading(true);
    setAddTransactionError(null);

    // Basic validation
    if (
      !newOrderData.user_id ||
      !newOrderData.total_amount ||
      newOrderData.items.length === 0
    ) {
      setAddTransactionError("Please fill in all required fields.");
      setAddTransactionLoading(false);
      return;
    }

    // Filter out empty items
    const validItems = newOrderData.items.filter(
      (item) => item.product_id && item.quantity && item.price
    );
    if (validItems.length === 0) {
      setAddTransactionError("Please add at least one valid item.");
      setAddTransactionLoading(false);
      return;
    }

    try {
      const payload = {
        user_id: newOrderData.user_id,
        total_amount: newOrderData.total_amount,
        items: validItems,
      };

      await apiClient.post("/merch/orders", payload);
      alert("Transaction added successfully!");
      setShowAddForm(false); // Hide form after success
      setNewOrderData({
        // Reset form data
        user_id: "",
        total_amount: "",
        items: [{ product_id: "", quantity: "", price: "" }],
      });
      fetchTransactions(); // Refresh the list
    } catch (err) {
      setAddTransactionError(
        "Failed to add transaction: " +
          (err.response?.data?.error ||
            err.response?.data?.message ||
            err.message)
      );
      console.error("Error adding transaction:", err.response || err);
    } finally {
      setAddTransactionLoading(false);
    }
  };

  if (loading) {
    return (
      <div className="min-h-screen flex bg-gray-900 text-white justify-center items-center">
        Loading transactions...
      </div>
    );
  }

  if (error) {
    return (
      <div className="min-h-screen flex bg-gray-900 text-white justify-center items-center text-red-500">
        Error: {error}
      </div>
    );
  }

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
        <div className="flex items-center justify-between mb-6">
          <h1 className="text-4xl font-bold text-[#ba3554]">Transactions</h1>
          <div className="flex items-center space-x-4">
            <select
              className="bg-gray-800 text-white border border-gray-600 rounded p-2"
              value={filter}
              onChange={handleFilterChange}
            >
              <option>Last 30 days</option>
              <option>Last 7 days</option>
              <option>Last 90 days</option>
              <option>All time</option>
            </select>
            <button
              onClick={() => setShowAddForm(!showAddForm)}
              className="bg-green-600 hover:bg-green-700 text-white font-bold py-2 px-4 rounded-lg shadow-md transition duration-200 ease-in-out transform hover:scale-105"
            >
              {showAddForm ? "Hide Form" : "Add New Transaction"}
            </button>
          </div>
        </div>

        {/* Add Transaction Form */}
        {showAddForm && (
          <div className="bg-gray-800 p-6 rounded-lg shadow-lg mb-8 max-w-2xl mx-auto">
            <h2 className="text-2xl font-bold mb-4 text-[#ba3554] text-center">
              Add New Order
            </h2>
            {addTransactionError && (
              <p className="text-red-500 text-center mb-4">
                {addTransactionError}
              </p>
            )}
            <form onSubmit={handleAddTransactionSubmit}>
              <div className="mb-4">
                <label
                  htmlFor="user_id"
                  className="block text-gray-300 text-sm font-bold mb-2"
                >
                  User ID:
                </label>
                <input
                  type="number"
                  id="user_id"
                  name="user_id"
                  value={newOrderData.user_id}
                  onChange={handleNewOrderChange}
                  className="shadow appearance-none border rounded w-full py-2 px-3 text-white leading-tight focus:outline-none focus:shadow-outline bg-gray-700 border-gray-600"
                  placeholder="e.g., 1 (must be an existing user ID)"
                  required
                />
              </div>
              <div className="mb-4">
                <label
                  htmlFor="total_amount"
                  className="block text-gray-300 text-sm font-bold mb-2"
                >
                  Total Amount:
                </label>
                <input
                  type="number"
                  id="total_amount"
                  name="total_amount"
                  value={newOrderData.total_amount}
                  onChange={handleNewOrderChange}
                  className="shadow appearance-none border rounded w-full py-2 px-3 text-white leading-tight focus:outline-none focus:shadow-outline bg-gray-700 border-gray-600"
                  step="0.01"
                  placeholder="e.g., 150.75"
                  required
                />
              </div>

              <h3 className="text-xl font-semibold mb-3 text-gray-200">
                Order Items:
              </h3>
              {newOrderData.items.map((item, index) => (
                <div key={index} className="flex space-x-2 mb-3 items-end">
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
                      className="shadow appearance-none border rounded w-full py-2 px-3 text-white leading-tight focus:outline-none focus:shadow-outline bg-gray-700 border-gray-600 text-sm"
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
                      className="shadow appearance-none border rounded w-full py-2 px-3 text-white leading-tight focus:outline-none focus:shadow-outline bg-gray-700 border-gray-600 text-sm"
                      placeholder="e.g., 2"
                      required
                    />
                  </div>
                  <div className="flex-1">
                    <label
                      htmlFor={`price-${index}`}
                      className="block text-gray-400 text-xs font-bold mb-1"
                    >
                      Price (at time):
                    </label>
                    <input
                      type="number"
                      id={`price-${index}`}
                      name="price"
                      value={item.price}
                      onChange={(e) => handleItemChange(index, e)}
                      className="shadow appearance-none border rounded w-full py-2 px-3 text-white leading-tight focus:outline-none focus:shadow-outline bg-gray-700 border-gray-600 text-sm"
                      step="0.01"
                      placeholder="e.g., 50.00"
                      required
                    />
                  </div>
                  {newOrderData.items.length > 1 && (
                    <button
                      type="button"
                      onClick={() => handleRemoveItem(index)}
                      className="bg-red-600 hover:bg-red-700 text-white p-2 rounded-lg text-sm"
                      title="Remove Item"
                    >
                      &times;
                    </button>
                  )}
                </div>
              ))}
              <button
                type="button"
                onClick={handleAddItem}
                className="bg-blue-600 hover:bg-blue-700 text-white font-bold py-2 px-4 rounded-lg shadow-md transition duration-200 ease-in-out transform hover:scale-105 mt-2"
              >
                Add Another Item
              </button>

              <div className="flex justify-center mt-6 space-x-4">
                <button
                  type="submit"
                  className="bg-purple-600 hover:bg-purple-700 text-white font-bold py-2 px-6 rounded-lg shadow-md transition duration-200 ease-in-out transform hover:scale-105"
                  disabled={addTransactionLoading}
                >
                  {addTransactionLoading ? "Adding..." : "Submit Order"}
                </button>
                <button
                  type="button"
                  onClick={() => setShowAddForm(false)}
                  className="bg-gray-600 hover:bg-gray-700 text-white font-bold py-2 px-6 rounded-lg shadow-md transition duration-200 ease-in-out transform hover:scale-105"
                >
                  Cancel
                </button>
              </div>
            </form>
          </div>
        )}

        {/* Transactions Table */}
        <div className="overflow-x-auto">
          {transactions.length > 0 ? (
            <table className="w-full border-collapse bg-gray-800 rounded-xl overflow-hidden shadow-md">
              <thead className="bg-gray-700 text-white">
                <tr>
                  <th className="p-3 text-left">Order ID</th>
                  <th className="p-3 text-left">User ID</th>
                  <th className="p-3 text-left">Status</th>
                  <th className="p-3 text-left">Date</th>
                  <th className="p-3 text-right">Total Cost</th>
                </tr>
              </thead>
              <tbody>
                {transactions.map((transaction) => (
                  <tr
                    key={transaction.id}
                    className="bg-gray-600 hover:bg-gray-500 transition-colors"
                  >
                    <td className="p-3">{transaction.id}</td>
                    <td className="p-3">{transaction.user_id}</td>
                    <td className="p-3">{transaction.status}</td>
                    <td className="p-3">
                      {new Date(transaction.created_at).toLocaleDateString()}
                    </td>
                    <td className="p-3 text-right">
                      ${transaction.total_amount.toFixed(2)}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          ) : (
            <div className="text-center py-8 text-gray-400">
              No transactions found for the selected period.
            </div>
          )}
        </div>
      </div>
    </div>
  );
};

export default TransactionsPage;
