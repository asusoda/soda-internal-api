import React from 'react';
import ReactDOM from 'react-dom/client';
import './index.css';
import App from './App';

// Import error suppression utility for ResizeObserver and other harmless errors
import './utils/errorSuppression';

const root = ReactDOM.createRoot(document.getElementById('root')!);
root.render(
  <React.StrictMode>
    <App />
  </React.StrictMode>
);

