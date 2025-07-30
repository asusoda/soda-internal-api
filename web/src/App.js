import './App.css';
import './index.css';

import BotControlPanel from "./pages/BotControlPanel";
import GamePanel from "./pages/GamePanel";
import Jeopardy from "./pages/Jeopardy";
import ActiveGame from './pages/ActiveGame';
import LoginPage from './pages/LoginPage';
import ServerError from './pages/ServerError';
import AddPoints from './pages/AddPoints';
import OCPDetails from './pages/OCPDetails';
import OrganizationSelector from './pages/OrganizationSelector';
import SuperAdmin from './pages/SuperAdmin';

import React from 'react';
import { Route, Routes, BrowserRouter } from 'react-router-dom';
import { ToastContainer } from 'react-toastify';
import 'react-toastify/dist/ReactToastify.css';
import TokenRetrival from './pages/TokenRetrival';
import HomePage from './pages/HomePage';
import UserPage from './pages/UserPage';
import LeaderBoard from './pages/LeaderBoard';

import { AuthProvider } from './components/auth/AuthContext';
import PrivateRoute from './components/auth/PrivateRoute';

function App() {
  
  return (
    <BrowserRouter>
      <AuthProvider>
        <Routes>
          {/* Public routes */}
          <Route path='/' element={<LoginPage/>} />
          <Route path='/login' element={<LoginPage/>} />
          <Route path='/auth' element={<TokenRetrival />} />
          <Route path='/500' element={<ServerError />} />
          
          {/* Organization selection */}
          <Route 
            path='/select-organization' 
            element={
              <PrivateRoute>
                <OrganizationSelector />
              </PrivateRoute>
            } 
          />
          
          {/* SuperAdmin route */}
          <Route 
            path='/superadmin' 
            element={
              <PrivateRoute>
                <SuperAdmin />
              </PrivateRoute>
            } 
          />
          
          {/* Legacy routes (for backward compatibility) */}
          <Route 
            path='/panel' 
            element={
              <PrivateRoute>
                <BotControlPanel />
              </PrivateRoute>
            } 
          />
          <Route 
            path='/addpoints' 
            element={
              <PrivateRoute>
                <AddPoints />
              </PrivateRoute>
            } 
          />
          <Route 
            path='/gamepanel' 
            element={
              <PrivateRoute>
                <GamePanel />
              </PrivateRoute>
            } 
          />
          <Route 
            path='/activegame' 
            element={
              <PrivateRoute>
                <ActiveGame />
              </PrivateRoute>
            } 
          />
          <Route 
            path='/jeopardy' 
            element={
              <PrivateRoute>
                <Jeopardy />
              </PrivateRoute>
            } 
          />
          <Route 
            path='/home' 
            element={
              <PrivateRoute>
                <HomePage/>
              </PrivateRoute>
            } 
          />
          <Route 
            path='/users' 
            element={
              <PrivateRoute>
                <UserPage />
              </PrivateRoute>
            } 
          />
          <Route 
            path='/leaderboard' 
            element={
              <PrivateRoute>
                <LeaderBoard />
              </PrivateRoute>
            } 
          />
          <Route 
            path='/ocp' 
            element={
              <PrivateRoute>
                <OCPDetails />
              </PrivateRoute>
            } 
          />
          
          {/* Organization-specific routes */}
          <Route 
            path='/:orgPrefix/dashboard' 
            element={
              <PrivateRoute>
                <HomePage/>
              </PrivateRoute>
            } 
          />
          <Route 
            path='/:orgPrefix/panel' 
            element={
              <PrivateRoute>
                <BotControlPanel />
              </PrivateRoute>
            } 
          />
          <Route 
            path='/:orgPrefix/addpoints' 
            element={
              <PrivateRoute>
                <AddPoints />
              </PrivateRoute>
            } 
          />
          <Route 
            path='/:orgPrefix/gamepanel' 
            element={
              <PrivateRoute>
                <GamePanel />
              </PrivateRoute>
            } 
          />
          <Route 
            path='/:orgPrefix/activegame' 
            element={
              <PrivateRoute>
                <ActiveGame />
              </PrivateRoute>
            } 
          />
          <Route 
            path='/:orgPrefix/jeopardy' 
            element={
              <PrivateRoute>
                <Jeopardy />
              </PrivateRoute>
            } 
          />
          <Route 
            path='/:orgPrefix/users' 
            element={
              <PrivateRoute>
                <UserPage />
              </PrivateRoute>
            } 
          />
          <Route 
            path='/:orgPrefix/leaderboard' 
            element={
              <PrivateRoute>
                <LeaderBoard />
              </PrivateRoute>
            } 
          />
          <Route 
            path='/:orgPrefix/ocp' 
            element={
              <PrivateRoute>
                <OCPDetails />
              </PrivateRoute>
            } 
          />
        </Routes>
        <ToastContainer />
      </AuthProvider>
    </BrowserRouter>
  );
}

export default App;
