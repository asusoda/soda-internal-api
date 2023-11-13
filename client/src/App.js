import './App.css';
import './index.css';

import BotControlPanel from "./components/BotControlPanel";
import GamePanel from "./components/GamePanel";
import React from 'react';
import { createBrowserRouter, createRoutesFromElements, Route, RouterProvider, Routes } from 'react-router-dom';
import { ToastContainer } from 'react-toastify';
import 'react-toastify/dist/ReactToastify.css';

function App() {
  return (
    <Routes>
      <Route path="/" element={<BotControlPanel />} />
      <Route path="/gamepanel/" element={<GamePanel />} />
    </Routes>
  );
}

export default App;
