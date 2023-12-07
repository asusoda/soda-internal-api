import './App.css';
import './index.css';

import BotControlPanel from "./pages/BotControlPanel";
import GamePanel from "./pages/GamePanel";
import Jeopardy from "./pages/Jeopardy";
import ActiveGame from './pages/ActiveGame';
import Legacy from './legacy/App';
import React from 'react';
import { Route, Routes, BrowserRouter } from 'react-router-dom';
import { ToastContainer } from 'react-toastify';
import 'react-toastify/dist/ReactToastify.css';

function App() {
  return (
    <Routes>
      <Route path='/' element={<Legacy />} />
      <Route path='/panel' element={<BotControlPanel />} />
      <Route path='/gamepanel/' element={<GamePanel />} />
      <Route path='/activegame/' element = {<ActiveGame />} />
      <Route path='/jeopardy' element= {<Jeopardy />} />
    </Routes>
  );
}

export default App;
