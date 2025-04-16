import React from 'react';
import { Link } from 'react-router-dom';

function GameCard({ game }) {
    return (
        <div className="bg-gray-700 text-white p-4 rounded-lg shadow-lg m-4 w-60 h-60 flex flex-col justify-between">
            <div>
                <h2 className="text-2xl font-bold mb-2">{game.name}</h2>
                <p className="mb-2">{game.description}</p>
            </div>
            <Link 
                to={`/gamepanel?uuid=${game.uuid}`}
                className="bg-blue-500 hover:bg-blue-600 text-white font-bold py-2 px-4 rounded text-center block"
            >
                View Game
            </Link>
        </div>
    );
}

export default GameCard;
