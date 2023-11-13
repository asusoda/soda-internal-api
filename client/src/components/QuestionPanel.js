import React from 'react';
import axios from 'axios';
import { toast } from 'react-toastify';

function QuestionPanel({ question, uuid }) {
  const setActiveGame = async () => {
    try {
      const response = await axios.post(`/api/setactivegame?uuid=${uuid}`);
      toast.success(response.data.message);
    } catch (error) {
      toast.error(error.response?.data?.error || 'An error occurred while setting the active game.');
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
    </div>
  );
}

export default QuestionPanel;
