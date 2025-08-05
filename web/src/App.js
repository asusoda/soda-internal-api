import "./App.css";
import "./index.css";

import BotControlPanel from "./pages/BotControlPanel";
import GamePanel from "./pages/GamePanel";
import Jeopardy from "./pages/Jeopardy";
import ActiveGame from "./pages/ActiveGame";
import LoginPage from "./pages/LoginPage";
import ServerError from "./pages/ServerError";
import AddPoints from "./pages/AddPoints";
import OCPDetails from "./pages/OCPDetails";
import OrganizationSelector from "./pages/OrganizationSelector";
import SuperAdmin from "./pages/SuperAdmin";

import React from "react";
import { Route, Routes, BrowserRouter, Navigate } from "react-router-dom";
import { ToastContainer } from "react-toastify";
import "react-toastify/dist/ReactToastify.css";
import TokenRetrival from "./pages/TokenRetrival";
import HomePage from "./pages/HomePage";
import UserPage from "./pages/UserPage";
import LeaderBoard from "./pages/LeaderBoard";
import CreateUserPage from "./pages/CreateUserPage";
import MerchandiseListPage from "./pages/MerchandiseListPage";
import AddMerchandisePage from "./pages/AddMerchandisePage";
import TransactionsPage from "./pages/TransactionsPage";
import MetricsPage from "./pages/MetricsPage";
import { AuthProvider } from "./components/auth/AuthContext";
import PrivateRoute from "./components/auth/PrivateRoute";

function App() {
  return (
    <BrowserRouter>
      <AuthProvider>
        <Routes>
          {/* Public routes */}
          <Route path="/" element={<LoginPage />} />
          <Route path="/login" element={<LoginPage />} />
          <Route path="/auth" element={<TokenRetrival />} />
          <Route path="/500" element={<ServerError />} />
          <Route path="/createuser" element={<CreateUserPage />} />
          <Route path="/merch/products" element={<MerchandiseListPage />} />
          <Route path="/merch/products/add" element={<AddMerchandisePage />} />
          <Route path="/transactions" element={<TransactionsPage />} />
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
            path="/:orgPrefix/panel"
            element={
              <PrivateRoute>
                <BotControlPanel />
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
            path="/:orgPrefix/gamepanel"
            element={
              <PrivateRoute>
                <GamePanel />
              </PrivateRoute>
            }
          />
          <Route
            path="/:orgPrefix/activegame"
            element={
              <PrivateRoute>
                <ActiveGame />
              </PrivateRoute>
            }
          />
          <Route
            path="/:orgPrefix/jeopardy"
            element={
              <PrivateRoute>
                <Jeopardy />
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
          <Route
            path="/:orgPrefix/ocp"
            element={
              <PrivateRoute>
                <OCPDetails />
              </PrivateRoute>
            }
          />

          {/* Legacy routes (for backward compatibility) - redirect to select-organization */}
          <Route
            path="/panel"
            element={<Navigate to="/select-organization" />}
          />
          <Route
            path="/addpoints"
            element={<Navigate to="/select-organization" />}
          />
          <Route
            path="/gamepanel"
            element={<Navigate to="/select-organization" />}
          />
          <Route
            path="/activegame"
            element={<Navigate to="/select-organization" />}
          />
          <Route
            path="/jeopardy"
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
          <Route path="/ocp" element={<Navigate to="/select-organization" />} />
        </Routes>
        <ToastContainer />
      </AuthProvider>
    </BrowserRouter>
  );
}

export default App;
