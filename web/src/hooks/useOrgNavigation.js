import { useNavigate } from "react-router-dom";
import { useAuth } from "../components/auth/AuthContext";

const useOrgNavigation = () => {
  const navigate = useNavigate();
  const { currentOrg } = useAuth();

  // Get organization-aware path
  const getOrgPath = (path) => {
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
  const navigateToOrg = (path, options = {}) => {
    const orgPath = getOrgPath(path);
    navigate(orgPath, options);
  };

  // Common navigation functions
  const goToDashboard = () => navigateToOrg("dashboard");
  const goToUsers = () => navigateToOrg("users");
  const goToLeaderboard = () => navigateToOrg("leaderboard");
  const goToAddPoints = () => navigateToOrg("addpoints");
  const goToPanel = () => navigateToOrg("panel");
  const goToOCP = () => navigateToOrg("ocp");
  const goToJeopardy = () => navigateToOrg("jeopardy");
  const goToGamePanel = () => navigateToOrg("gamepanel");
  const goToActiveGame = () => navigateToOrg("activegame");
  const goToMerchProducts = () => navigateToOrg("merch/products");
  const goToAddProducts = () => navigateToOrg("merch/products/add");
  const goToOrders = () => navigateToOrg("/transactions");

  return {
    navigateToOrg,
    getOrgPath,
    currentOrg,
    // Common navigation functions
    goToDashboard,
    goToUsers,
    goToLeaderboard,
    goToAddPoints,
    goToPanel,
    goToOCP,
    goToJeopardy,
    goToGamePanel,
    goToActiveGame,
    goToMerchProducts,
    goToAddProducts,
  };
};

export default useOrgNavigation;
