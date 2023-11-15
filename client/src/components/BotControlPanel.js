import React, { useState, useEffect } from 'react';
import axios from 'axios';
import { toast, ToastContainer } from 'react-toastify';
import 'react-toastify/dist/ReactToastify.css';
import GameCard from './GameCard';
import UploadFileCard from './UploadFileCard';
function BotControlPanel() {
    const [botStatus, setBotStatus] = useState(false); // false indicates 'OFF', true indicates 'ON'
    const [games, setGames] = useState([]);
    const [activeGame, setActiveGame] = useState(null); // New state for active game
    useEffect(() => {
        // Function to fetch bot status
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
        // Function to fetch available games
       
        fetchGames();
        fetchActiveGame();
    }, []);

    const ActiveGamePanel = () => (
        <div className="bg-green-300 text-gray-800 p-4 rounded-lg shadow-lg m-4 cursor-pointer">
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
            toast.success(response.data.message);
            setBotStatus(!botStatus);
        } catch (error) {
            toast.error(`Error toggling the bot. Please try again.`);
            console.error('Error:', error);
        }
    };

    const fetchGames = async () => {
        try {
            const response = await axios.get('/api/getavailablegames');
            setGames(response.data);
        } catch (error) {
            console.error('Error fetching games:', error);
            toast.error('Error fetching games. Please try again.' + error);
        }
    };
    const handleFileSelect = (event) => {
        const file = event.target.files[0];
        if (file) {
            uploadFile(file);
        }
    };

    const uploadFile = (file) => {
        const formData = new FormData();
        formData.append('file', file);

        axios.post('/api/uploadgame', formData)
            .then(response => {
                toast.success(response.data.message);
                // Optionally, refresh the list of games after successful upload
            })
            .catch(error => {
                toast.error(error.response.data.error || 'Upload failed');
            });
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
            {games.map(game => (
                <GameCard key={game.file_name} game={game} />
            ))}
            <UploadFileCard onFileSelect={handleFileSelect} />
            <ToastContainer 
                position="top-right"
                autoClose={5000}
                hideProgressBar={false}
                newestOnTop={false}
                closeOnClick
                rtl={false}
                pauseOnFocusLoss
                draggable
                pauseOnHover
            />
        </div>
        
    );
}

export default BotControlPanel;
