// ErrorPage.js
import React from 'react';
import { Link } from 'react-router-dom';

function ServerError() {
  return (
    <div className="flex flex-col items-center justify-center min-h-screen bg-red-100 text-red-800">
      <h1 className="text-4xl font-bold mb-4">500 - Internal Server Error</h1>
      <p className="text-lg mb-8">Oops! Something went wrong on our end. Please try again later.</p>
      <Link 
        to="/" 
        className="text-blue-500 hover:text-blue-700 underline text-lg"
      >
        Go back to Home
      </Link>
    </div>
  );
}

export default ServerError;
