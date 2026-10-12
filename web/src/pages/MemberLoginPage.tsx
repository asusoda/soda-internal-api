import { useNavigate, useParams } from "react-router-dom";
import { FaDiscord, FaUser } from "react-icons/fa";
import { storeLoginUrl } from "../components/utils/memberClient";

// Member sign-in for the store: a Discord sign-in through the API, which returns to the store.
const MemberLoginPage = () => {
  const { orgPrefix } = useParams();
  const navigate = useNavigate();

  return (
    <div className="min-h-screen bg-black flex items-center justify-center px-4">
      <div className="max-w-md w-full">
        <div className="text-center mb-8">
          <div className="mx-auto w-16 h-16 bg-gradient-to-br from-blue-500 to-purple-600 rounded-full flex items-center justify-center mb-4">
            <FaUser className="text-white text-2xl" />
          </div>
          <h1 className="text-3xl font-bold text-white mb-2">Member Login</h1>
          <p className="text-gray-400">
            Sign in with the Discord account that is in the org's server
          </p>
        </div>

        <div className="bg-gray-900 rounded-xl border border-gray-700 p-6">
          <a
            href={orgPrefix ? storeLoginUrl(orgPrefix) : undefined}
            className="w-full bg-indigo-600 hover:bg-indigo-700 text-white font-semibold py-3 px-4 rounded-lg transition-colors flex items-center justify-center"
          >
            <FaDiscord className="mr-2" />
            Login with Discord
          </a>

          <div className="mt-4 text-center">
            <button
              onClick={() => navigate(`/store/${orgPrefix}`)}
              className="text-gray-400 hover:text-white text-sm transition-colors"
            >
              ← Back to Store
            </button>
          </div>
        </div>
      </div>
    </div>
  );
};

export default MemberLoginPage;
