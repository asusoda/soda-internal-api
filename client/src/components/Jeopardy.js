import React, { useState, useEffect } from 'react';
import axios from 'axios';
import { ToastContainer, toast } from 'react-toastify';
import { Link } from 'react-router-dom';

function GameCard({ game }) {
    return (
        <div className="bg-gray-700 text-white p-4 rounded-lg shadow-lg m-4 w-60 h-60 flex flex-col justify-between">
            <div>
                <h2 className="text-2xl font-bold mb-2">{game.name}</h2>
                <p className="mb-2">{game.description}</p>
            </div>
            <Link 
                to={`/gamepanel?name=${game.name}`}
                className="bg-blue-500 hover:bg-blue-600 text-white font-bold py-2 px-4 rounded text-center block"
            >
                View Game
            </Link>
        </div>
    );
}

function UploadFileCard({ onFileSelect }) {
    return (
        <div className="bg-gray-700 text-white p-4 rounded-lg shadow-lg m-4 w-60 h-60 flex flex-col justify-center items-center cursor-pointer hover:bg-gray-600">
            <input type="file" accept=".json" onChange={onFileSelect} hidden id="fileUpload" />
            <label htmlFor="fileUpload" className="text-3xl mb-2">+</label>
            <label htmlFor="fileUpload">Upload New Game</label>
        </div>
    );
}



function Jeoprardy(){

    const [games, setGames] = useState([]);
    const [activeGame, setActiveGame] = useState(null);


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

    const fetchGames = async () => {
        try {
            const response = await axios.get('/api/getavailablegames');
            setGames(response.data);
        } catch (error) {
            console.error('Error fetching games:', error);
            toast.error('Error:' + error);
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

    useEffect(() => {
        fetchGames();
        fetchActiveGame();
    }, []);

    return (
        <div className="bg-gray-800 text-gray-200 min-h-screen p-4">
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

export default Jeoprardy;