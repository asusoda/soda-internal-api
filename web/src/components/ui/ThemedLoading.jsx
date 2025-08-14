import React from 'react';
import Orb from './Orb';

const ThemedLoading = ({ message = "Loading..." }) => {
  return (
    <div className="relative min-h-screen bg-black text-white overflow-hidden flex items-center justify-center">
      {/* Background Effects */}
      <div className="absolute inset-0">
        <Orb hue={300} forceHoverState={true} hoverIntensity={0.1} />
      </div>

      {/* Loading Content */}
      <div className="relative z-10 text-center">
        <div className="flex flex-col items-center space-y-6">
          {/* Spinner */}
          <div className="relative">
            <div className="w-16 h-16 border-4 border-gray-700 border-t-blue-500 rounded-full animate-spin"></div>
            <div className="absolute inset-0 w-16 h-16 border-4 border-transparent border-t-purple-500 rounded-full animate-spin" style={{ animationDelay: '-0.5s' }}></div>
          </div>
          
          {/* Loading Text */}
          <div className="space-y-2">
            <h2 className="text-xl font-semibold text-white">{message}</h2>
            <p className="text-sm text-gray-400">Please wait while we load your content...</p>
          </div>
        </div>
      </div>
    </div>
  );
};

export default ThemedLoading; 