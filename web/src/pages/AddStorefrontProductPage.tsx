import { useState, type FormEvent } from "react";
import { useParams } from "react-router-dom";
import axios from "axios";
import apiClient from "../components/utils/axios";
import OrganizationNavbar from "../components/shared/OrganizationNavbar";
import { FaPlus } from "react-icons/fa";
import { toast } from "react-toastify";
import { useAuth } from "../components/auth/AuthContext";
import { PRODUCT_CATEGORIES } from "../constants/productCategories";
import type { ApiError } from "../types";

const AddStorefrontProductPage = () => {
  const { orgPrefix } = useParams();
  const { currentOrg } = useAuth();
  const [imageUrl, setImageUrl] = useState("");
  const [name, setName] = useState("");
  const [price, setPrice] = useState("");
  const [stock, setStock] = useState<number | string>(1);
  const [description, setDescription] = useState("");
  const [category, setCategory] = useState("");
  const [isAddingNewCategory, setIsAddingNewCategory] = useState(false);
  const [newCategoryInput, setNewCategoryInput] = useState("");

  // Predefined categories (shared constant) - extract values only
  const predefinedCategories = PRODUCT_CATEGORIES
    .map((cat) => cat.value)
    .filter(Boolean); // Remove empty string option

  // Load custom categories from localStorage
  const [customCategories, setCustomCategories] = useState<string[]>(() => {
    const saved = localStorage.getItem('customCategories');
    if (!saved) {
      return [];
    }

    try {
      const parsed: unknown = JSON.parse(saved);
      return Array.isArray(parsed) ? parsed.filter((cat): cat is string => typeof cat === 'string') : [];
    } catch (error) {
      console.error('Failed to parse customCategories from localStorage:', error);
      return [];
    }
  });

  const allCategories = [...predefinedCategories, ...customCategories];

  const handleAddNewCategory = () => {
    if (newCategoryInput.trim()) {
      // Format: lowercase and replace spaces with hyphens
      const formatted = newCategoryInput.trim().toLowerCase().replace(/\s+/g, '-');
      
      if (!allCategories.includes(formatted)) {
        const updated = [...customCategories, formatted];
        setCustomCategories(updated);
        localStorage.setItem('customCategories', JSON.stringify(updated));
        setCategory(formatted);
        toast.success(`Category "${formatted}" added!`);
      } else {
        toast.info("Category already exists");
        setCategory(formatted);
      }
      
      setNewCategoryInput("");
      setIsAddingNewCategory(false);
    }
  };

  const handleSubmit = async (e: FormEvent<HTMLFormElement>) => {
    e.preventDefault();

    const prefixToUse = orgPrefix || currentOrg?.prefix;
    if (!prefixToUse) {
      toast.error("No organization selected");
      return;
    }

    const productData = {
      name,
      description,
      price: parseFloat(price), // Use parseFloat for decimal prices
      stock: parseInt(String(stock)),
      image_url: imageUrl,
      category: category || null,
    };

    try {
      // Updated API endpoint to include organization prefix
      await apiClient.post(`/api/storefront/${prefixToUse}/products`, productData);
      toast.success("Product added successfully!");
      // Reset form
      setImageUrl("");
      setName("");
      setPrice("");
      setStock(1);
      setDescription("");
      setCategory("");
    } catch (error) {
      console.error("Error submitting form:", error);
      const data = axios.isAxiosError<ApiError>(error) ? error.response?.data : undefined;
      const errorMessage = data?.error || 
        data?.message ||
        "Something went wrong while adding the product.";
      toast.error(errorMessage);
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
      <div className="max-w-xl mx-auto">
        <div className="text-center mb-8">
          <h1 className="text-3xl font-bold mb-2">Add New Product</h1>
          <p className="text-gray-400">
            Add a new item to {currentOrg.name}'s storefront
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
                rows={3}
              />
            </div>

            <div>
              <label className="block text-sm font-medium text-gray-300 mb-1">
                Category
              </label>
              
              {!isAddingNewCategory ? (
                <div className="flex gap-2">
                  <select
                    value={category}
                    onChange={(e) => {
                      if (e.target.value === "__add_new__") {
                        setIsAddingNewCategory(true);
                      } else {
                        setCategory(e.target.value);
                      }
                    }}
                    className="flex-1 px-3 py-2 bg-gray-800 border border-gray-600 rounded-md text-white focus:outline-none focus:border-green-500"
                  >
                    <option value="">Select a category (optional)</option>
                    <optgroup label="Standard Categories">
                      {predefinedCategories.map(cat => {
                        const label = cat
                          .split('-')
                          .map(word => word.charAt(0).toUpperCase() + word.slice(1))
                          .join(' ');
                        return (
                          <option key={cat} value={cat}>
                            {label}
                          </option>
                        );
                      })}
                    </optgroup>
                    {customCategories.length > 0 && (
                      <optgroup label="Custom Categories">
                        {customCategories.map(cat => {
                          const label = cat
                            .split('-')
                            .map(word => word.charAt(0).toUpperCase() + word.slice(1))
                            .join(' ');
                          return (
                            <option key={cat} value={cat}>
                              {label}
                            </option>
                          );
                        })}
                      </optgroup>
                    )}
                    <option value="__add_new__" className="text-green-400">+ Add New Category</option>
                  </select>
                </div>
              ) : (
                <div className="flex gap-2">
                  <input
                    type="text"
                    value={newCategoryInput}
                    onChange={(e) => setNewCategoryInput(e.target.value)}
                    onKeyDown={(e) => {
                      if (e.key === 'Enter') {
                        e.preventDefault();
                        handleAddNewCategory();
                      }
                    }}
                    placeholder="e.g., Accessories"
                    className="flex-1 px-3 py-2 bg-gray-800 border border-gray-600 rounded-md text-white placeholder-gray-400 focus:outline-none focus:border-green-500"
                    autoFocus
                  />
                  <button
                    type="button"
                    onClick={handleAddNewCategory}
                    className="px-4 py-2 bg-green-600 hover:bg-green-700 text-white rounded-md transition-colors"
                  >
                    Add
                  </button>
                  <button
                    type="button"
                    onClick={() => {
                      setIsAddingNewCategory(false);
                      setNewCategoryInput("");
                    }}
                    className="px-4 py-2 bg-gray-600 hover:bg-gray-700 text-white rounded-md transition-colors"
                  >
                    Cancel
                  </button>
                </div>
              )}
              
              {category && (
                <p className="text-xs text-gray-400 mt-1">
                  Selected: <span className="text-white">{category}</span>
                </p>
              )}
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

export default AddStorefrontProductPage;
