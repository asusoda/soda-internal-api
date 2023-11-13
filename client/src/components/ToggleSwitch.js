// src/components/ToggleSwitch.js

import React, { useState } from 'react';

function ToggleSwitch() {
  const [isOn, setIsOn] = useState(false);

  const toggleBot = async () => {
  
  };

  return (
    <div className="toggle-section">
      <label className="toggle-switch">
        <input type="checkbox" checked={isOn} onChange={toggleBot} />
        <span className="slider"></span>
      </label>
      <p>Bot: <span>{isOn ? 'ON' : 'OFF'}</span></p>
    </div>
  );
}

export default ToggleSwitch;
