import React, { useState, useEffect } from 'react';
import axios from 'axios';
import { toast, ToastContainer } from 'react-toastify';
import 'react-toastify/dist/ReactToastify.css';
import { useNavigate, Link } from 'react-router-dom';

function FeatureCard({ title, link, icon }) {

    const navigate = useNavigate();

    const handleClick = () => {
        navigate(`/${link}`);
    };

    return (
        console.log(icon, title, link),
        <div className="w-40 h-40 bg-blue-300 text-gray-800 p-4 rounded-lg shadow-lg m-4 flex flex-col items-center justify-center cursor-pointer" onClick={handleClick}>
            <img src={`/static/${icon}`} alt={`${title} icon`} className="w-12 h-12 mb-2" />
            <h2 className="text-xl font-bold text-center">{title}</h2>
        </div>
    );
}


function BotControlPanel() {
    const [botStatus, setBotStatus] = useState(false); 
    const [activeGame, setActiveGame] = useState(null); 
    const [features, setFeatures] = useState([]);

    useEffect(() => {
        const fetchBotStatus = async () => {
            try {
                const response = await axios.get('/api/botstatus');
                setBotStatus(response.data.status);
            } catch (error) {
                toast.error('Error fetching bot status.');
                console.error('Error:', error);
            }
        };
        fetchBotStatus();
    }, []);

    useEffect(() => {
        axios.get('/api/getfeatures')
            .then(response => {
                setFeatures(response.data);
            })
            .catch(error => {
                console.error('Error fetching features:', error);
                // handle error
            });
            fetchActiveGame();
    }, []);
   

    const navigate = useNavigate();
    const handleClick = () => {
        navigate('/activegame/');
      };

    const ActiveGamePanel = () => (
        <div className="bg-green-300 text-gray-800 p-4 rounded-lg shadow-lg m-4 cursor-pointer" onClick={handleClick}>
            <h2 className="text-2xl font-bold">Active Game: {activeGame.game.name}</h2>
            <p>Click to go to the game</p>
        </div>
    );

    const fetchActiveGame = async () => {
        try {
            const response = await axios.get('/api/getactivegame');
             console.log(response.data);
            setActiveGame(response.data); // Set active game data
        } catch (error) {
            console.error('Error fetching active game:', error);
            setActiveGame(null); // Ensure active game is null if fetch fails
        }
    };
    

    const toggleBot = async () => {
        const url = botStatus ? '/api/stopbot' : '/api/startbot';
        try {
            const response = await axios.post(url);
            console.log(response.data);
            toast.success(response.data.message);
            setBotStatus(!botStatus);
        } catch (error) {
            toast.error(`Error toggling the bot. Please try again.`);
            console.error('Error:', error);
        }
    };

    
    

    
    
    return (
        <div className="bg-gray-800 text-gray-200 min-h-screen p-4">
            <div className="navbar flex justify-between items-center bg-gray-700 p-3 rounded">
                <div className="toggle-section flex items-center">
                    <label className="toggle-switch relative w-14 h-8 mr-2">
                        <input 
                            type="checkbox" 
                            className="sr-only"
                            checked={botStatus}
                            onChange={toggleBot} 
                        />
                        <span className="slider block bg-gray-600 rounded-full h-full w-full transition"></span>
                        <span className={`dot absolute left-1 bottom-1 bg-blue-500 rounded-full h-6 w-6 transition-transform ${botStatus ? 'translate-x-6' : ''}`}></span>
                    </label>
                    <p className="text-lg">Bot Status: <span className="font-semibold">{botStatus ? 'ON' : 'OFF'}</span></p>
                </div>
                <a href="/logout/" className="text-blue-400 hover:text-blue-300 transition">Logout</a>
            </div>
            {activeGame && <ActiveGamePanel />}
            <div className="flex flex-wrap gap-4">
            {Object.entries(features).map(([featureName, featureData]) => (
                    <FeatureCard title={featureName} link={featureData.link} icon={featureData.img} />
                ))}
            </div>
            <ToastContainer />
        </div>
        
    );
}

export default BotControlPanel;
