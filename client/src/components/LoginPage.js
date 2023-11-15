import React from 'react';
const LoginPage = () => {

 
      const handle_login = () => {
        window.location.href = 'http://localhost:5000/login/';
      };
  return (
    console.log("Login Page"),
    <div className="flex justify-center items-center h-screen bg-gray-100">
        <div className="absolute w-full h-full">
      <div className="p-10 bg-white shadow-xl rounded-lg">
        <h1 className="text-2xl font-bold text-gray-700 mb-4">Welcome to the Home Page!</h1>
        <a href="/login" className="inline-block">
          <button className="bg-blue-500 hover:bg-blue-700 text-white font-bold py-2 px-4 rounded" onClick={handle_login}>
            Login with Discord
          </button>
        </a>
      </div>
    </div>
    </div>
  );
};

export default LoginPage;
