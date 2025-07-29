import React from 'react';

function RevealQuestion({ question, onRevealQuestion }) {
  return (
    <div className="p-4 bg-gray-700 mt-4 rounded shadow">
      <h2 className="text-xl font-bold">{question.category}</h2>
      <p className="mb-2">{question.question}</p>
      <button
        className="mt-4 bg-lime-300 text-white font-bold py-2 px-4 rounded hover:bg-pastel-green-300"
        onClick={() => onRevealQuestion(question.id)}
      >
        Reveal Question
      </button>
    </div>
  );
}

export default RevealQuestion;