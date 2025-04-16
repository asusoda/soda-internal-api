import React, { useState, useEffect } from 'react';
import axios from 'axios';
import { useLocation } from 'react-router-dom';
import { toast, ToastContainer } from 'react-toastify';

function ActiveGameModal({ isOpen, onClose, onConfirm, gameName }) {
  const [date, setDate] = useState('');
  const [time, setTime] = useState('');

  const handleSubmit = () => {
    onConfirm(gameName, date, time);
    onClose();
  };
 
  return (
    <div className={`modal ${isOpen ? 'block' : 'hidden'}`}>
      <div className="modal-content">
        <span className="close" onClick={onClose}>&times;</span>
        <h2>Set Active Game Time</h2>
        <input type="date" value={date} onChange={(e) => setDate(e.target.value)} className="w-full p-2 mb-2 border border-gray-300 rounded input-type" />
        <input type="time" value={time} onChange={(e) => setTime(e.target.value)} className="w-full p-2 mb-4 border border-gray-300 rounded input-type" />
        <button onClick={handleSubmit} className="w-full bg-blue-500 text-white p-2 rounded hover:bg-blue-600">Confirm</button>
      </div>
    </div>
  );
}


function GameBoard({ categories, onQuestionClick }) {
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

  function QuestionPanel({ question, name }) {
    const [modalOpen, setModalOpen] = useState(false);

    const setActiveGame = async (name, date, time) => {
      try {
        if (botStatus === false) {
          toast.error('Please start the bot before setting the active game.');
          return;
        }
        const response = await axios.post(`/api/setactivegame?name=${name}&date=${date}&time=${time}`);
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
        onClick={() => setModalOpen(true)}
      >
        Set as Active Game
      </button>
      <ActiveGameModal
        isOpen={modalOpen}
        onClose={() => setModalOpen(false)}
        onConfirm={setActiveGame}
        gameName={name}
      />
        <ToastContainer />
      </div>
    );
  }
  

  function GamePanel() {
    const [gameData, setGameData] = useState(null);
    const [selectedQuestion, setSelectedQuestion] = useState(null);
    const location = useLocation();
    const queryParams = new URLSearchParams(location.search);
    const gameName = queryParams.get('name'); // assuming 'name' is the query parameter used

    useEffect(() => {
        if (gameName) {
            axios.get(`/api/getgame?name=${gameName}`)
                .then(response => {
                    setGameData(response.data);
                })
                .catch(error => {
                    console.error('Error fetching game data:', error);
                    toast.error('Error fetching game data');
                });
        }
    }, [gameName]);

    if (!gameData) {
        return (
            <div className="flex justify-center items-center h-screen">
                <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-gray-900"></div>
            </div>
        );
    }

    const handleQuestionClick = (question) => {
        setSelectedQuestion(question);
    };

    return (
        <div className="p-6 bg-gray-800 min-h-screen text-white">
            <h1 className="text-3xl font-bold mb-4">{gameData.info.name}</h1>
            <p>{gameData.info.description}</p>
            <p>Players: {gameData.info.players}</p>
            <p>Teams: {gameData.info.teams.join(", ")}</p>
            <GameBoard categories={gameData.questions} onQuestionClick={handleQuestionClick} />
            <QuestionPanel question={selectedQuestion} name={gameName} />
            <ToastContainer />
        </div>
    );
}

export default GamePanel;
