import React, { useState, useEffect } from 'react';
import axios from 'axios';
import { useLocation } from 'react-router-dom';
import { toast, ToastContainer } from 'react-toastify';


function GameBoard({ uuid, onQuestionClick }) {
    const [categories, setCategories] = useState({});
  
    useEffect(() => {
      // Fetch the questions from the API when the component mounts
      const fetchQuestions = async () => {
        try {
          const response = await axios.get(`/api/getgamequestions?uuid=${uuid}`);
          setCategories(response.data);
        } catch (error) {
          console.error('Error fetching questions:', error);
          // Handle the error, e.g., show an error message
        }
      };
  
      fetchQuestions();
    }, []);
  
    return (
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 xl:grid-cols-5 gap-4 p-4">
        {/* Loop through each category and its questions */}
        {Object.entries(categories).map(([category, questions]) => (
          <div key={category} className="flex flex-col">
            <h2 className="text-center font-bold mb-2">{category}</h2>
            <div className="grid grid-cols-1 gap-2">
              {questions.map((question) => (
                <button
                  key={question.uuid}
                  className="text-lg bg-gray-700 hover:bg-gray-600 text-white p-4 rounded shadow"
                  onClick={() => onQuestionClick(question)}
                >
                  {question.value}
                </button>
              ))}
            </div>
          </div>
        ))}
      </div>
    );
  }

  function QuestionPanel({ question, uuid }) {
    const setActiveGame = async () => {
      try {
        if (botStatus === false) {
          toast.error('Please start the bot before setting the active game.');
          return;
        }
        const response = await axios.post(`/api/setactivegame?uuid=${uuid}`);
        toast.success(response.data.message);
      } catch (error) {
        toast.error(error.response?.data?.error || 'An error occurred while setting the active game.');
      }
    };
    
    const botStatus = async () => {
      try {
        const response = await axios.get('/api/botstatus');
         botStatus(response.data.status);
      } catch (error) {
        toast.error('Error fetching bot status.');
        console.error('Error:', error);
      }
    }
    return (
      <div className="p-4 bg-gray-700 mt-4 rounded shadow">
        {question ? (
          <>
            <h2 className="text-xl font-bold">Question</h2>
            <p className="mb-2">{question.question}</p>
            <h2 className="text-xl font-bold">Answer</h2>
            <p>{question.answer}</p>
          </>
        ) : (
          <p>Select a question to view its details.</p>
        )}
        {/* Button to set the game as active */}
        <button
          className="mt-4 bg-lime-300 text-white font-bold py-2 px-4 rounded hover:bg-pastel-green-300"
          onClick={setActiveGame}
        >
          Set as Active Game
        </button>
        <ToastContainer />
      </div>
    );
  }
  

function GamePanel() {
    const [gameData, setGameData] = useState(null);
    const [selectedQuestion, setSelectedQuestion] = useState(null);
    const location = useLocation();
    const queryParams = new URLSearchParams(location.search);
    const uuid = queryParams.get('uuid');
    const Spinner = () => {
        return (
          <div className="flex justify-center items-center">
            <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-gray-900"></div>
          </div>
        );
      };
      
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
        return <Spinner />;
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
