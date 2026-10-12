import { useState, useEffect, type ChangeEvent, type FormEvent } from "react";
import apiClient from "./utils/axios"; // Adjust path if necessary
import { toast } from "react-toastify";
import { PRODUCT_CATEGORIES } from "../constants/productCategories";
import { errorDetail, type Product } from "../storefrontTypes";

interface EditProductModalProps {
  product: Product | null;
  onClose: () => void;
  onProductUpdated: () => void;
  organizationPrefix: string | undefined;
}

// The form fields. Price and stock are empty strings until the product loads or the officer types a number.
interface ProductFormData {
  name: string;
  description: string | null;
  price: number | string;
  stock: number | string;
  image_url: string | null;
  category: string;
}

const EditProductModal = ({ product, onClose, onProductUpdated, organizationPrefix }: EditProductModalProps) => {
  const [formData, setFormData] = useState<ProductFormData>({
    name: "",
    description: "",
    price: "",
    stock: "",
    image_url: "",
    category: "",
  });
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [isAddingNewCategory, setIsAddingNewCategory] = useState(false);
  const [newCategoryInput, setNewCategoryInput] = useState("");

  // Predefined categories (shared) - extract values only
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
      return Array.isArray(parsed) ? parsed.filter((cat): cat is string => typeof cat === "string") : [];
    } catch (e) {
      console.error('Failed to parse customCategories from localStorage', e);
      return [];
    }
  });

  const allCategories = [...predefinedCategories, ...customCategories];

  const handleAddNewCategory = () => {
    if (newCategoryInput.trim()) {
      // Format: lowercase and replace spaces with hyphens
      const formatted = newCategoryInput.trim().toLowerCase().replace(/\s+/g, '-');
      
      const categoryExists = allCategories.includes(formatted);

      if (!categoryExists) {
        const updated = [...customCategories, formatted];
        setCustomCategories(updated);
        localStorage.setItem('customCategories', JSON.stringify(updated));
        setFormData(prev => ({ ...prev, category: formatted }));
        toast.success(`Category "${formatted}" added!`);
      } else {
        toast.info("Category already exists");
        setFormData(prev => ({ ...prev, category: formatted }));
      }
      
      setNewCategoryInput("");
      setIsAddingNewCategory(false);
    }
  };

  useEffect(() => {
    // Populate form data when the product prop changes (i.e., when modal opens for a new product)
    if (product) {
      setFormData({
        name: product.name,
        description: product.description,
        price: product.price,
        stock: product.stock,
        image_url: product.image_url,
        category: product.category || "",
      });
    }
  }, [product]);

  const handleChange = (e: ChangeEvent<HTMLInputElement | HTMLTextAreaElement | HTMLSelectElement>) => {
    const { name, value } = e.target;
    setFormData((prevData) => ({
      ...prevData,
      [name]: name === "price" || name === "stock" ? Number(value) : value,
    }));
  };

  const handleSubmit = async (e: FormEvent<HTMLFormElement>) => {
    e.preventDefault();
    if (!product) return;
    
    if (!organizationPrefix) {
      toast.error("No organization selected");
      return;
    }
    
    setLoading(true);
    setError(null);
    try {
      await apiClient.put(`/api/storefront/${organizationPrefix}/products/${product.id}`, formData);
      toast.success("Product updated successfully!");
      onProductUpdated(); // Notify parent component to refresh products
      onClose(); // Close the modal
    } catch (err) {
      const errorMessage = "Failed to update product. " + errorDetail(err);
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
              value={formData.description ?? ""}
              onChange={handleChange}
              className="shadow appearance-none border rounded w-full py-2 px-3 text-white leading-tight focus:outline-none focus:shadow-outline bg-gray-700 border-gray-600 h-24"
            ></textarea>
          </div>
          <div className="mb-4">
            <label
              htmlFor="category"
              className="block text-gray-300 text-sm font-bold mb-2"
            >
              Category:
            </label>
            
            {!isAddingNewCategory ? (
              <div className="flex gap-2">
                <select
                  id="category"
                  name="category"
                  value={formData.category}
                  onChange={(e) => {
                    if (e.target.value === "__add_new__") {
                      setIsAddingNewCategory(true);
                    } else {
                      handleChange(e);
                    }
                  }}
                  className="flex-1 shadow appearance-none border rounded py-2 px-3 text-white leading-tight focus:outline-none focus:shadow-outline bg-gray-700 border-gray-600"
                >
                  <option value="">Select a category (optional)</option>
                  <optgroup label="Standard Categories">
                    {predefinedCategories.map((cat, index) => {
                      const formattedLabel = cat
                        .split("-")
                        .map(word => word.charAt(0).toUpperCase() + word.slice(1))
                        .join(" ");
                      return (
                        <option key={cat || index} value={cat}>
                          {formattedLabel}
                        </option>
                      );
                    })}
                  </optgroup>
                  {customCategories.length > 0 && (
                    <optgroup label="Custom Categories">
                      {customCategories.map(cat => (
                        <option key={cat} value={cat}>
                          {cat.split('-').map(word => word.charAt(0).toUpperCase() + word.slice(1)).join(' ')}
                        </option>
                      ))}
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
                  className="flex-1 shadow appearance-none border rounded py-2 px-3 text-white leading-tight focus:outline-none focus:shadow-outline bg-gray-700 border-gray-600"
                  autoFocus
                />
                <button
                  type="button"
                  onClick={handleAddNewCategory}
                  className="px-4 py-2 bg-green-600 hover:bg-green-700 text-white rounded transition-colors"
                >
                  Add
                </button>
                <button
                  type="button"
                  onClick={() => {
                    setIsAddingNewCategory(false);
                    setNewCategoryInput("");
                  }}
                  className="px-4 py-2 bg-gray-600 hover:bg-gray-700 text-white rounded transition-colors"
                >
                  Cancel
                </button>
              </div>
            )}
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
              value={formData.image_url ?? ""}
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
