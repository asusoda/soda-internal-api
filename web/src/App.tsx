import "./App.css";
import "./index.css";

import LoginPage from "./pages/LoginPage";
import ServerError from "./pages/ServerError";
import AddPoints from "./pages/AddPoints";
import OrganizationSelector from "./pages/OrganizationSelector";
import SuperAdmin from "./pages/SuperAdmin";
import Calendar from "./pages/Calendar";
import ComputePage from "./pages/ComputePage";
import PodFilesPage from "./pages/PodFilesPage";

import { Route, Routes, BrowserRouter, Navigate } from "react-router-dom";
import { ToastContainer } from "react-toastify";
import "react-toastify/dist/ReactToastify.css";
import TokenRetrival from "./pages/TokenRetrival";
import HomePage from "./pages/HomePage";
import UserPage from "./pages/UserPage";
import LeaderBoard from "./pages/LeaderBoard";
import StorefrontListPage from "./pages/StorefrontListPage";
import AddStorefrontProductPage from "./pages/AddStorefrontProductPage";
import TransactionsPage from "./pages/TransactionsPage";
import StorefrontDashboard from "./pages/StorefrontDashboard";
import MemberStorePage from "./pages/MemberStorePage";
import MemberLoginPage from "./pages/MemberLoginPage";
import MetricsPage from "./pages/MetricsPage";
import { AuthProvider } from "./components/auth/AuthContext";
import PrivateRoute from "./components/auth/PrivateRoute";
import ErrorBoundary from "./components/ErrorBoundary";

function App() {
  return (
    <ErrorBoundary>
      <BrowserRouter>
        <AuthProvider>
          <Routes>
          {/* Public routes */}
          <Route path="/" element={<LoginPage />} />
          <Route path="/login" element={<LoginPage />} />
          <Route path="/auth" element={<TokenRetrival />} />
          <Route path="/500" element={<ServerError />} />
          
          {/* Member store (public browsing, auth required for ordering) */}
          <Route path="/store/:orgPrefix" element={<MemberStorePage />} />
          <Route path="/store/:orgPrefix/login" element={<MemberLoginPage />} />
          
          {/* Private storefront management routes */}
          <Route
            path="/:orgPrefix/storefront/dashboard"
            element={
              <PrivateRoute>
                <StorefrontDashboard />
              </PrivateRoute>
            }
          />
          <Route
            path="/:orgPrefix/storefront/products"
            element={
              <PrivateRoute>
                <StorefrontListPage />
              </PrivateRoute>
            }
          />
          <Route
            path="/:orgPrefix/add-storefront-product"
            element={
              <PrivateRoute>
                <AddStorefrontProductPage />
              </PrivateRoute>
            }
          />
          <Route
            path="/:orgPrefix/transactions"
            element={
              <PrivateRoute>
                <TransactionsPage />
              </PrivateRoute>
            }
          />
          <Route path="/metrics" element={<MetricsPage />} />
          {/* Organization selection - landing page for authenticated users */}
          <Route
            path="/select-organization"
            element={
              <PrivateRoute>
                <OrganizationSelector />
              </PrivateRoute>
            }
          />

          {/* SuperAdmin route */}
          <Route
            path="/superadmin"
            element={
              <PrivateRoute>
                <SuperAdmin />
              </PrivateRoute>
            }
          />

          {/* Organization-specific routes */}
          <Route
            path="/:orgPrefix/dashboard"
            element={
              <PrivateRoute>
                <HomePage />
              </PrivateRoute>
            }
          />
          <Route
            path="/:orgPrefix/calendar"
            element={
              <PrivateRoute>
                <Calendar />
              </PrivateRoute>
            }
          />
          <Route
            path="/:orgPrefix/addpoints"
            element={
              <PrivateRoute>
                <AddPoints />
              </PrivateRoute>
            }
          />
          <Route
            path="/:orgPrefix/compute"
            element={
              <PrivateRoute>
                <ComputePage />
              </PrivateRoute>
            }
          />
          <Route
            path="/:orgPrefix/compute/:podId/files"
            element={
              <PrivateRoute>
                <PodFilesPage />
              </PrivateRoute>
            }
          />
          <Route
            path="/:orgPrefix/users"
            element={
              <PrivateRoute>
                <UserPage />
              </PrivateRoute>
            }
          />
          <Route
            path="/:orgPrefix/leaderboard"
            element={
              <PrivateRoute>
                <LeaderBoard />
              </PrivateRoute>
            }
          />

          {/* Legacy routes (for backward compatibility) - redirect to select-organization */}
          <Route
            path="/addpoints"
            element={<Navigate to="/select-organization" />}
          />
          <Route
            path="/home"
            element={<Navigate to="/select-organization" />}
          />
          <Route
            path="/users"
            element={<Navigate to="/select-organization" />}
          />
          <Route
            path="/leaderboard"
            element={<Navigate to="/select-organization" />}
          />
          {/* Unknown paths, such as the removed game and bot pages */}
          <Route path="*" element={<Navigate to="/select-organization" replace />} />
          </Routes>
          <ToastContainer />
        </AuthProvider>
      </BrowserRouter>
    </ErrorBoundary>
  );
}

export default App;
