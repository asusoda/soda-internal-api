import React, { useState, useEffect } from 'react';
import axios from 'axios';
import { ToastContainer, toast } from 'react-toastify';


const GameBoard = ({ data, onQuestionSelect }) => {
    return (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 xl:grid-cols-5 gap-4 p-4">
            {Object.entries(data).map(([category, questions]) => (
                <div key={category} className="flex flex-col">
                    <h2 className="text-center font-bold mb-2">{category}</h2>
                    <div className="grid grid-cols-1 gap-2">
                        {questions.map((question) => (
                            <button
                                key={question.id}
                                className={`text-lg bg-gray-700 hover:bg-gray-600 text-white p-4 rounded shadow ${question.answered ? 'opacity-50' : ''}`}
                                onClick={() => onQuestionSelect(question)}
                                disabled={question.answered}
                            >
                                {question.value}
                            </button>
                        ))}
                    </div>
                </div>
            ))}
        </div>
    );
};


const QuestionPanel = ({ question, teams }) => {
    const [selectedTeam, setSelectedTeam] = useState('');

    const handleRevealQuestion = async () => {
        if (!question) {
            toast.error('Please select a question');
            return;
        }

        try {
            const response = await axios.post('/api/revealquestion', null, {
                params: {
                    uuid: question.id
                }
            });
            toast.success(response.data.message);
        } catch (error) {
            console.error('Error revealing question:', error);
            toast.error('Error revealing question');
        }
    };

    const handleRevealAnswer = async () => {
        if (!question) {
            toast.error('Please select a question');
            return;
        }

        try {
            const response = await axios.post('/api/revealanswer', null, {
                params: {
                    uuid: question.id
                }
            });
            toast.success(response.data.message);
        } catch (error) {
            console.error('Error revealing answer:', error);
            toast.error('Error revealing answer');
        }
    };

    const handleAwardPoints = async () => {
        if (!selectedTeam || !question) {
            toast.error('Please select a team and a question');
            return;
        }

        try {
            const response = await axios.post('/api/awardpoints', null,{
                params: {
                    team: selectedTeam,
                    points: question.value
                }
            });

            toast.success(response.data.message);
        } catch (error) {
            console.error('Error awarding points:', error);
            toast.error('Error awarding points');
        }
    };

    return (
        <div className="p-4 bg-gray-700 mt-4 rounded shadow">
            {question ? (
                <>
                    <h2 className="text-xl font-bold">Question</h2>
                    <p className="mb-2">{question.question}</p>
                    <h2 className="text-xl font-bold">Answer</h2>
                    <p>{question.answer}</p>
                    <button onClick={handleRevealQuestion} className="bg-blue-500 text-white p-2 rounded mt-2">Reveal Question</button>
                    &nbsp;&nbsp;&nbsp;
                    <button onClick={handleRevealAnswer} className="bg-green-500 text-white p-2 rounded mt-2">Reveal Answer</button>
                    &nbsp;&nbsp;&nbsp;
                    <select 
                            onChange={(e) => setSelectedTeam(e.target.value)} 
                            className="mt-2 bg-white text-black"
                        >
                            {teams.map((team) => (
                                <option key={team.name} value={team.name}>{team.name}</option>
                            ))}
                        </select>
                    &nbsp;&nbsp;&nbsp;
                    <button onClick={handleAwardPoints} className="bg-yellow-500 text-white p-2 rounded mt-2">Award Points</button>
                </>
            ) : (
                <p>Select a question to view its details.</p>
            )}
        </div>
    );
};

const Spinner = () => {
    return (
        <div className="flex justify-center items-center h-screen bg-gray-800">
            <div className="animate-spin rounded-full h-12 w-12 border-b-4 border-white"></div>
        </div>
    );
};

const ActiveGamePanel = () => {
    const [activeGameData, setActiveGameData] = useState(null);
    const [selectedQuestion, setSelectedQuestion] = useState(null);

    useEffect(() => {
        const fetchActiveGameData = async () => {
            try {
                const response = await axios.get('/api/getactivegame');
                setActiveGameData(response.data);
            } catch (error) {
                console.error('Error fetching active game data:', error);
                toast.error('Error fetching active game data');
            }
        };

        fetchActiveGameData();
    }, []);

    const handleQuestionSelect = (question) => {
        setSelectedQuestion(question);
    };

    const handleCreateChannels = async () => {
        try {
            const response = await axios.post('/api/createchannels');
            
        }
        catch (error) {
            console.error('Error creating channels:', error);
            toast.error('Error creating channels');
        }
    }
    const handleEndGame = () => {
        // Implement end game logic
    }
    const SetupButton = () => {
        const handleCreateChannelsAndAnnounce = async () => {
            try {
                const response = await axios.post('/api/createchannels');
                toast.success('Channels created and game announced');
            } catch (error) {
                console.error('Error creating channels and announcing game:', error);
                toast.error('Error creating channels and announcing game');
            }
        };
    
        const handleStartGame = async () => {
            try {
                const response = await axios.post('/api/startactivegame');
                toast.success('Game started successfully');
            } catch (error) {
                console.error('Error starting the game:', error);
                toast.error('Error starting the game');
            }
        };
    
        if (!activeGameData.game.announced) {
            return (
                <button onClick={handleCreateChannelsAndAnnounce} className="bg-blue-500 text-white p-2 rounded mt-2">
                    Create Channels and Announce Game
                </button>
            );
        } else {
            return (
                <button onClick={handleStartGame} className="bg-green-500 text-white p-2 rounded mt-2">
                    Start Game
                </button>
            );
        }
    };;

    if (!activeGameData) {
        return <Spinner />;
    }

    return (
        

        <div className="p-6 bg-gray-800 min-h-screen text-white">
             <div className="navbar flex justify-between items-center bg-gray-700 p-3 rounded">
             <SetupButton />
             
            <button onClick={handleEndGame} className="bg-red-500 text-white p-2 rounded mt-2">End Game and Delete Channels</button>
             </div>
            <h1 className="text-3xl font-bold mb-4">{activeGameData.game.name}</h1>
            <p>{activeGameData.game.description}</p>
            <GameBoard data={activeGameData.questions} onQuestionSelect={handleQuestionSelect} />
            <QuestionPanel question={selectedQuestion} teams={activeGameData.game.teams} />
            <ToastContainer />
        </div>
    );
};

export default ActiveGamePanel;