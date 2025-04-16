import React, { useState } from 'react';
import axios from 'axios';
import { toast } from 'react-toastify';

function QuestionPanel({ question, teams, onAwardPoints }) {
  const [answerVisible, setAnswerVisible] = useState(false);
  const [selectedTeam, setSelectedTeam] = useState('');

  const handleRevealClick = () => {
    setAnswerVisible(true);
  };

  const handleAnswerClick = () => {
    setAnswerVisible(false);
  };

  const handleAwardPoints = async () => {
    if (!selectedTeam) {
      toast.error('Please select a team first.');
      return;
    }

    try {
      // Replace with your actual endpoint and request structure
      const response = await axios.post('/api/awardpoints', {
        team: selectedTeam,
        questionId: question.id,
      });
      toast.success(response.data.message);
      onAwardPoints(); // Callback to update the parent state
    } catch (error) {
      toast.error(error.response?.data?.error || 'An error occurred while awarding points.');
    }
  };

  return (
    <div className="p-4 bg-gray-700 mt-4 rounded shadow">
      <h2 className="text-xl font-bold">Question</h2>
      <p className="mb-2">{question.question}</p>

      {answerVisible && (
        <>
          <h2 className="text-xl font-bold">Answer</h2>
          <p>{question.answer}</p>
        </>
      )}

      <div className="flex items-center justify-between my-4">
        <button
          className="bg-blue-500 hover:bg-blue-600 text-white font-bold py-2 px-4 rounded"
          onClick={handleRevealClick}
        >
          Reveal
        </button>
        <button
          className="bg-green-500 hover:bg-green-600 text-white font-bold py-2 px-4 rounded"
          onClick={handleAnswerClick}
        >
          Answer
        </button>
      </div>

      <div className="my-4">
        <select
          className="bg-gray-800 text-white p-2 rounded"
          value={selectedTeam}
          onChange={(e) => setSelectedTeam(e.target.value)}
        >
          <option value="">Select Team</option>
          {teams.map((team) => (
            <option key={team} value={team}>{team}</option>
          ))}
        </select>

        <button
          className="bg-lime-500 hover:bg-lime-600 text-white font-bold py-2 px-4 rounded ml-2"
          onClick={handleAwardPoints}
        >
          Award To
        </button>
      </div>
    </div>
  );
}

export default QuestionPanel;
