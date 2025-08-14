import React, { useCallback } from "react";
import {
  FaUser,
  FaChartLine,
  FaDiscord,
  FaHome,
  FaPlus,
  FaCogs,
  FaClipboardList,
  FaTshirt,
  FaExchangeAlt,
} from "react-icons/fa";
import { useNavigate } from "react-router-dom";
import useOrgNavigation from "../hooks/useOrgNavigation";
import OrganizationSwitcher from "./OrganizationSwitcher";
import { debounce } from "../utils/resizeObserverFix";
import "./SideBar.css";

const Sidebar = ({ isSidebarOpen, toggleSidebar }) => {
  const {
    goToDashboard,
    goToUsers,
    goToLeaderboard,
    goToAddPoints,
    goToOCP,
    currentOrg,
  } = useOrgNavigation();

  const navigate = useNavigate();

  // Debounce the sidebar toggle to prevent rapid state changes
  const debouncedToggle = useCallback(
    debounce(() => {
      toggleSidebar();
    }, 150),
    [toggleSidebar]
  );

  return (
    <div
      className={`sidebar ${isSidebarOpen ? "open" : ""}`}
      style={{ backgroundColor: "#ba3554" }}
    >
      <button className="close-btn" onClick={debouncedToggle}>
        {isSidebarOpen ? "✖" : "☰"}
      </button>

      {/* Organization switcher when sidebar is open */}
      {isSidebarOpen && currentOrg && (
        <div className="px-3 py-2 border-b border-white/20 mb-2">
          <OrganizationSwitcher className="w-full" />
        </div>
      )}

      <div className={`sidebar-links ${isSidebarOpen ? "visible" : "hidden"}`}>
        <button onClick={goToDashboard}>
          <FaHome className="icon" />
          {isSidebarOpen && <span>Dashboard</span>}
        </button>

        <button onClick={goToUsers}>
          <FaUser className="icon" />
          {isSidebarOpen && <span>Users</span>}
        </button>

        <button onClick={goToLeaderboard}>
          <FaChartLine className="icon" />
          {isSidebarOpen && <span>Leaderboard</span>}
        </button>

        <button onClick={goToAddPoints}>
          <FaPlus className="icon" />
          {isSidebarOpen && <span>Add Points</span>}
        </button>
        <button onClick={() => navigate("/merch/products")}>
          <FaTshirt className="icon" />
          {isSidebarOpen && <span>Merchandise</span>}
        </button>
        <button onClick={() => navigate("/merch/products/add")}>
          <FaPlus className="icon" />
          {isSidebarOpen && <span>Add Merchandise</span>}
        </button>
        <button onClick={() => navigate("/transactions")}>
          <FaExchangeAlt className="icon" />
          {isSidebarOpen && <span>Transactions</span>}
        </button>
        <button onClick={goToOCP}>
          <FaClipboardList className="icon" />
          {isSidebarOpen && <span>OCP Details</span>}
        </button>

        {/* Organization info when collapsed */}
        {!isSidebarOpen && currentOrg && (
          <div className="org-indicator" title={currentOrg.name}>
            {currentOrg.icon_url ? (
              <img
                src={currentOrg.icon_url}
                alt={currentOrg.name}
                className="w-6 h-6 rounded-full"
              />
            ) : (
              <div className="w-6 h-6 bg-white/20 rounded-full flex items-center justify-center text-xs">
                {currentOrg.prefix.toUpperCase()}
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  );
};

export default Sidebar;
