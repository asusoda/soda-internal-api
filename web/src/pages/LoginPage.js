import React from "react";
import { useNavigate } from "react-router-dom";
import Orb from "../components/ui/Orb"; // Import the Orb component
import StarBorder from "../components/ui/StarBorder"; // Import the StarBorder component
import Logo from "../assets/logo-dark.svg"; // Updated import path for the logo
import { FaDiscord, FaRocket, FaUsers, FaCog } from "react-icons/fa"; // Import icons

const LoginPage = () => {
  const navigate = useNavigate();

  // Function to handle login
  const handleLogin = () => {
    window.location.href = "https://api.thesoda.io/api/auth/login"; // Redirect to your Flask backend login route
  };

  // Function to handle bot invitation
  const handleInviteBot = () => {
    window.open(
      "https://discord.com/oauth2/authorize?client_id=1298753452171595847",
      "_blank"
    );
  };

  return (
    <div className="relative min-h-screen flex flex-col items-center justify-center bg-soda-black text-soda-white overflow-hidden">
      {/* Sticky Logo */}
      <div className="absolute top-0 left-0 p-4 md:p-6 z-20">
        <img src={Logo} alt="SoDA Admin Logo" className="w-32 md:w-40" />
      </div>

      <div className="absolute inset-0 z-0">
        <Orb hue={300} forceHoverState={true} hoverIntensity={0.1} />{" "}
        {/* Blue hue for the Orb */}
      </div>

      {/* Main Content Container */}
      <div className="relative z-10 max-w-5xl w-full border border-soda-white/20 rounded-xl backdrop-blur-xl flex flex-col lg:flex-row items-center justify-center gap-8 mt-16 md:mt-0">
        {/* Login Section */}
        <div className="max-w-md w-full p-8 rounded-lg flex flex-col items-center">
          <h1 className="text-3xl md:text-4xl font-bold mb-3 text-soda-white text-center">
            SoDA Admin Panel
          </h1>
          <p className="mb-8 text-center text-gray-300 text-sm md:text-base">
            Admin dashboard for SoDA management. Please log in to continue.
          </p>
          <div className="flex justify-center w-full">
            <StarBorder
              onClick={handleLogin}
              color="#FF3B30" // Red color for the star effect
              speed="5s"
              className="w-full max-w-xs"
            >
              <div className="flex items-center justify-center">
                <FaDiscord className="mr-2 h-5 w-5" />
                Login with Discord
              </div>
            </StarBorder>
          </div>
        </div>

        {/* Bot Invitation Section */}
        <div className="max-w-xl w-full p-8 bg-gradient-to-br from-purple-900/80 to-blue-900/80 rounded-lg shadow-2xl flex flex-col items-center border border-purple-500/30">
          <div className="flex items-center justify-center w-16 h-16 bg-purple-600 rounded-full mb-4">
            <FaRocket className="h-8 w-8 text-white" />
          </div>

          <h2 className="text-2xl md:text-3xl font-bold mb-3 text-white text-center">
            Add SoDA Bot
          </h2>

          <p className="mb-6 text-center text-gray-200 text-sm md:text-base">
            Invite our Discord bot to your community to unlock powerful
            management features.
          </p>

          {/* Features List */}
          <div className="w-full mb-6 space-y-3">
            <div className="flex items-center text-sm text-gray-200">
              <FaUsers className="h-4 w-4 mr-3 text-purple-400" />
              <span>Member management & points system</span>
            </div>
            <div className="flex items-center text-sm text-gray-200">
              <FaCog className="h-4 w-4 mr-3 text-purple-400" />
              <span>Custom commands & automation</span>
            </div>
            <div className="flex items-center text-sm text-gray-200">
              <FaDiscord className="h-4 w-4 mr-3 text-purple-400" />
              <span>Seamless Discord integration</span>
            </div>
          </div>

          <div className="flex justify-center w-full">
            <StarBorder
              onClick={handleInviteBot}
              color="#8B5CF6" // Purple color for the star effect
              speed="4s"
              className="w-full max-w-xs"
            >
              <div className="flex items-center justify-center">
                <FaDiscord className="mr-2 h-5 w-5" />
                Invite Bot to Server
              </div>
            </StarBorder>
          </div>

          <p className="mt-4 text-xs text-gray-400 text-center">
            Requires Discord server admin permissions
          </p>
        </div>
      </div>
    </div>
  );
};

export default LoginPage;
