import './App.css';
import './index.css';

import BotControlPanel from "./components/BotControlPanel";
import GamePanel from "./components/GamePanel";
import LoginPage from "./components/LoginPage";
import ActiveGame from './components/ActiveGame';
import React from 'react';
import { Route, Routes, BrowserRouter } from 'react-router-dom';
import { ToastContainer } from 'react-toastify';
import 'react-toastify/dist/ReactToastify.css';

function App() {
  return (
    <Routes>
      <Route path="/panel/" element={<BotControlPanel />} />
      <Route path="/gamepanel/" element={<GamePanel />} />
      <Route path='/activegame/' element = {<ActiveGame />} />
   
    </Routes>
  );
}

export default App;
