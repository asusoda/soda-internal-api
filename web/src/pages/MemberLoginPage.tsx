import { useState, type ChangeEvent, type FormEvent } from "react";
import { useParams, useNavigate } from "react-router-dom";
import apiClient from "../components/utils/axios";
import { FaUser, FaSpinner, FaIdCard, FaEnvelope, FaGraduationCap, FaDiscord } from "react-icons/fa";
import { toast } from "react-toastify";
import axios from "axios";
import type { ApiError } from "../types";

// POST /api/points/<org_prefix>/member_login in modules/points/api.py.
interface MemberLoginResponse {
  message: string;
  user: {
    id: number;
    name: string | null;
    username: string | null;
    email: string | null;
    asu_id: string | null;
    discord_linked: boolean;
  };
  organization: {
    id: number;
    name: string;
    prefix: string;
  };
}

const MemberLoginPage = () => {
  const { orgPrefix } = useParams();
  const navigate = useNavigate();
  const [loading, setLoading] = useState(false);
  const [formData, setFormData] = useState({
    name: '',
    username: '',
    email: '',
    asu_id: '',
    academic_standing: '',
    major: ''
  });

  const handleInputChange = (e: ChangeEvent<HTMLInputElement | HTMLSelectElement>) => {
    const { name, value } = e.target;
    setFormData(prev => ({
      ...prev,
      [name]: value
    }));
  };

  const handleSubmit = async (e: FormEvent<HTMLFormElement>) => {
    e.preventDefault();
    
    if (!orgPrefix) {
      toast.error("Organization not specified");
      return;
    }

    // Validate required fields
    if (!formData.name || !formData.asu_id) {
      toast.error("Name and ASU ID are required");
      return;
    }

    setLoading(true);
    try {
      const response = await apiClient.post<MemberLoginResponse>(`/api/points/${orgPrefix}/member_login`, {
        ...formData
      });

      toast.success("Login successful!");
      
      // Store user info in localStorage for the member store
      localStorage.setItem('memberUser', JSON.stringify(response.data.user));
      localStorage.setItem('memberOrg', JSON.stringify(response.data.organization));
      
      // Redirect back to store
      navigate(`/store/${orgPrefix}`);
      
    } catch (error) {
      const data = axios.isAxiosError<ApiError>(error) ? error.response?.data : undefined;
      const errorMessage = data?.error || 
        data?.message || 
        "Login failed. Please try again.";
      toast.error(errorMessage);
      console.error("Login error:", error);
    } finally {
      setLoading(false);
    }
  };

  const handleDiscordLogin = () => {
    // Store the current org prefix for after Discord auth
    if (orgPrefix) sessionStorage.setItem('pendingMemberOrg', orgPrefix);
    window.location.href = '/auth';
  };

  return (
    <div className="min-h-screen bg-black flex items-center justify-center px-4">
      <div className="max-w-md w-full">
        <div className="text-center mb-8">
          <div className="mx-auto w-16 h-16 bg-gradient-to-br from-blue-500 to-purple-600 rounded-full flex items-center justify-center mb-4">
            <FaUser className="text-white text-2xl" />
          </div>
          <h1 className="text-3xl font-bold text-white mb-2">Member Login</h1>
          <p className="text-gray-400">
            Access the store and link your account
          </p>
        </div>

        <div className="bg-gray-900 rounded-xl border border-gray-700 p-6">
          <form onSubmit={handleSubmit} className="space-y-4">
            <div>
              <label className="block text-sm font-medium text-gray-300 mb-2">
                <FaUser className="inline mr-2" />
                Full Name *
              </label>
              <input
                type="text"
                name="name"
                value={formData.name}
                onChange={handleInputChange}
                className="w-full px-4 py-3 bg-gray-800 border border-gray-600 rounded-lg text-white placeholder-gray-400 focus:outline-none focus:border-blue-500 transition-colors"
                placeholder="Enter your full name"
                required
              />
            </div>

            <div>
              <label className="block text-sm font-medium text-gray-300 mb-2">
                <FaIdCard className="inline mr-2" />
                ASU ID *
              </label>
              <input
                type="text"
                name="asu_id"
                value={formData.asu_id}
                onChange={handleInputChange}
                className="w-full px-4 py-3 bg-gray-800 border border-gray-600 rounded-lg text-white placeholder-gray-400 focus:outline-none focus:border-blue-500 transition-colors"
                placeholder="Enter your ASU ID"
                required
              />
            </div>

            <div>
              <label className="block text-sm font-medium text-gray-300 mb-2">
                <FaUser className="inline mr-2" />
                Username
              </label>
              <input
                type="text"
                name="username"
                value={formData.username}
                onChange={handleInputChange}
                className="w-full px-4 py-3 bg-gray-800 border border-gray-600 rounded-lg text-white placeholder-gray-400 focus:outline-none focus:border-blue-500 transition-colors"
                placeholder="Choose a username"
              />
            </div>

            <div>
              <label className="block text-sm font-medium text-gray-300 mb-2">
                <FaEnvelope className="inline mr-2" />
                Email
              </label>
              <input
                type="email"
                name="email"
                value={formData.email}
                onChange={handleInputChange}
                className="w-full px-4 py-3 bg-gray-800 border border-gray-600 rounded-lg text-white placeholder-gray-400 focus:outline-none focus:border-blue-500 transition-colors"
                placeholder="Enter your email"
              />
            </div>

            <div>
              <label className="block text-sm font-medium text-gray-300 mb-2">
                <FaGraduationCap className="inline mr-2" />
                Academic Standing
              </label>
              <select
                name="academic_standing"
                value={formData.academic_standing}
                onChange={handleInputChange}
                className="w-full px-4 py-3 bg-gray-800 border border-gray-600 rounded-lg text-white focus:outline-none focus:border-blue-500 transition-colors"
              >
                <option value="">Select academic standing</option>
                <option value="Freshman">Freshman</option>
                <option value="Sophomore">Sophomore</option>
                <option value="Junior">Junior</option>
                <option value="Senior">Senior</option>
                <option value="Graduate">Graduate</option>
                <option value="PhD">PhD</option>
              </select>
            </div>

            <div>
              <label className="block text-sm font-medium text-gray-300 mb-2">
                <FaGraduationCap className="inline mr-2" />
                Major
              </label>
              <input
                type="text"
                name="major"
                value={formData.major}
                onChange={handleInputChange}
                className="w-full px-4 py-3 bg-gray-800 border border-gray-600 rounded-lg text-white placeholder-gray-400 focus:outline-none focus:border-blue-500 transition-colors"
                placeholder="Enter your major"
              />
            </div>

            <div className="pt-4">
              <button
                type="submit"
                disabled={loading}
                className="w-full bg-blue-600 hover:bg-blue-700 disabled:bg-gray-600 disabled:cursor-not-allowed text-white font-semibold py-3 px-4 rounded-lg transition-colors flex items-center justify-center"
              >
                {loading ? (
                  <FaSpinner className="animate-spin mr-2" />
                ) : (
                  <FaUser className="mr-2" />
                )}
                {loading ? "Logging in..." : "Login to Store"}
              </button>
            </div>
          </form>

          <div className="mt-6 pt-6 border-t border-gray-700">
            <div className="text-center">
              <p className="text-gray-400 text-sm mb-4">
                Have a Discord account? Link it for full access to points and features.
              </p>
              <button
                onClick={handleDiscordLogin}
                className="w-full bg-indigo-600 hover:bg-indigo-700 text-white font-semibold py-3 px-4 rounded-lg transition-colors flex items-center justify-center"
              >
                <FaDiscord className="mr-2" />
                Login with Discord
              </button>
            </div>
          </div>

          <div className="mt-4 text-center">
            <button
              onClick={() => navigate(`/store/${orgPrefix}`)}
              className="text-gray-400 hover:text-white text-sm transition-colors"
            >
              ← Back to Store
            </button>
          </div>
        </div>

        <div className="mt-6 text-center text-xs text-gray-500">
          <p>* Required fields</p>
          <p className="mt-2">
            Your information will be used to link your account and track your points and orders.
          </p>
        </div>
      </div>
    </div>
  );
};

export default MemberLoginPage;
