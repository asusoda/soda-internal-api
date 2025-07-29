import React from 'react';

function UploadFileCard({ onFileSelect }) {
    return (
        <div className="bg-gray-700 text-white p-4 rounded-lg shadow-lg m-4 w-60 h-60 flex flex-col justify-center items-center cursor-pointer hover:bg-gray-600">
            <input type="file" accept=".json" onChange={onFileSelect} hidden id="fileUpload" />
            <label htmlFor="fileUpload" className="text-3xl mb-2">+</label>
            <label htmlFor="fileUpload">Upload New Game</label>
        </div>
    );
}


export default UploadFileCard;
