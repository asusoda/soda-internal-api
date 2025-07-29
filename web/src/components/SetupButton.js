import React, { useState, useEffect } from 'react';
import axios from 'axios';
import { ToastContainer, toast } from 'react-toastify';

function SetupButton() {
    const [setup, setSetup] = useState(false);
    const [start, setStart] = useState(false);

    useEffect(() => {
        if (setup && !start) {
            handleStartGame();
        }
    }, [setup]); // This effect runs when 'setup' state changes

    const handleCreateChannelsAndAnnounce = async () => {
        try {
            const response = await axios.post('/api/createchannels');
            toast.success('Channels created and game announced');
            setSetup(true);
        } catch (error) {
            console.error('Error creating channels and announcing game:', error);
            toast.error('Error creating channels and announcing game');
        }
    };

    const handleStartGame = async () => {
        try {
            const response = await axios.post('/api/startactivegame');
            toast.success('Game started successfully');
            setStart(true);
        } catch (error) {
            console.error('Error starting the game:', error);
            toast.error('Error starting the game');
        }
    };

    if (!setup) {
        return (
            <button onClick={handleCreateChannelsAndAnnounce} className="bg-blue-500 text-white p-2 rounded mt-2">
                Create Channels and Announce Game
            </button>
        );
    } else if (setup && !start) {
        return (
            <button disabled className="bg-green-500 text-white p-2 rounded mt-2">
                Starting Game...
            </button>
        );
    } else {
        return (
            <button disabled className="bg-gray-500 text-white p-2 rounded mt-2">
                Game in Progress
            </button>
        );
    }
}

export default SetupButton;
