import { useNavigate, type NavigateOptions } from "react-router-dom";
import { useAuth } from "../components/auth/AuthContext";

const useOrgNavigation = () => {
  const navigate = useNavigate();
  const { currentOrg } = useAuth();

  // Get organization-aware path
  const getOrgPath = (path: string) => {
    if (!currentOrg) {
      // Fallback to legacy paths if no org context
      return path;
    }

    // Remove leading slash if present
    const cleanPath = path.startsWith("/") ? path.slice(1) : path;

    // Return org-prefixed path
    return `/${currentOrg.prefix}/${cleanPath}`;
  };

  // Organization-aware navigate function
  const navigateToOrg = (path: string, options: NavigateOptions = {}) => {
    const orgPath = getOrgPath(path);
    navigate(orgPath, options);
  };

  // Common navigation functions
  const goToDashboard = () => navigateToOrg("dashboard");
  const goToUsers = () => navigateToOrg("users");
  const goToLeaderboard = () => navigateToOrg("leaderboard");
  const goToAddPoints = () => navigateToOrg("addpoints");
  const goToStorefrontProducts = () => navigateToOrg("storefront/products");
  const goToAddProducts = () => navigateToOrg("add-storefront-product");
  const goToOrders = () => navigateToOrg("transactions");

  return {
    navigateToOrg,
    getOrgPath,
    currentOrg,
    // Common navigation functions
    goToDashboard,
    goToUsers,
    goToLeaderboard,
    goToAddPoints,
    goToStorefrontProducts,
    goToAddProducts,
    goToOrders,
  };
};

export default useOrgNavigation;
