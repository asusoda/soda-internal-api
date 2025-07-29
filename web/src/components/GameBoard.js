import React, { useState, useEffect } from 'react';
import axios from 'axios';

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

export default GameBoard;
