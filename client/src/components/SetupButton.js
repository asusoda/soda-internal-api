import React, { useState } from 'react';
import axios from 'axios';
import { ToastContainer, toast } from 'react-toastify';


function SetupButton() {

        const [setup, setSetup] = useState(false);
        const [start, setStart] = useState(false);
        const handleCreateChannelsAndAnnounce = async () => {
            try {
                const response = await axios.post('/api/createchannels');
                toast.success('Channels created and game announced');
                setSetup(true);
            } catch (error) {
                console.error('Error creating channels and announcing game:', error);
                toast.error('Error creating channels and announcing game');
            }
        }

        const handleStartGame = async () => {
            try {
                const response = await axios.post('/api/startgame');
                toast.success('Game started successfully');
                setStart(true);
            } catch (error) {
                console.error('Error starting the game:', error);
                toast.error('Error starting the game');
            }
        }


        if (!setup && !start) {
            return (
                <button onClick={handleCreateChannelsAndAnnounce} className="bg-blue-500 text-white p-2 rounded mt-2">
                    Create Channels and Announce Game
                </button>
            );
        }
        else if (setup && !start) {
            return (
                <button onClick={handleStartGame} className="bg-green-500 text-white p-2 rounded mt-2">
                    Start Game
                </button>
            );
        }
        else {
            return (
                <button className="bg-gray-500 text-white p-2 rounded mt-2">
                    Game in Progress
                </button>
            );
        }

    }

export default SetupButton;