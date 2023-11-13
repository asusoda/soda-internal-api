import React, { useState, useEffect } from 'react';
import axios from 'axios';
import { useLocation } from 'react-router-dom';
import { toast } from 'react-toastify';
import GameBoard from './GameBoard';
import QuestionPanel from './QuestionPanel';

function GamePanel() {
    const [gameData, setGameData] = useState(null);
    const [selectedQuestion, setSelectedQuestion] = useState(null);
    const location = useLocation();
    const queryParams = new URLSearchParams(location.search);
    const uuid = queryParams.get('uuid');

    useEffect(() => {
        if (uuid) {
            axios.get(`/api/getgameinfo?uuid=${uuid}`)
                .then(response => {
                    setGameData(response.data);
                })
                .catch(error => {
                    console.error('Error fetching game data:', error);
                    toast.error('Error fetching game data');
                });
        }
    }, [uuid]);

    if (!gameData) {
        return <div>Loading...</div>;
    }
    const handleQuestionClick = (question) => {
        setSelectedQuestion(question);
      };

    return (
        console.log(gameData),
        <div className="p-6 bg-gray-800 min-h-screen text-white">
            <h1 className="text-3xl font-bold mb-4">{gameData.name}</h1>
            <p>{gameData.description}</p>
            <p>Players: {gameData.players}</p>
            <p>Teams: {gameData.teams}</p>
            <GameBoard uuid={uuid} onQuestionClick={handleQuestionClick}/>
            <QuestionPanel uuid={uuid} question={selectedQuestion} />
        </div>
    );
}

export default GamePanel;
