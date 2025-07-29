import React, { useState, useRef } from 'react';
import axios from 'axios';
const AddPoints = () => {
  const [asuId, setAsuId] = useState('');
  const [comment, setComment] = useState('');
  const asuIdInputRef = useRef(null);

  const handleSubmit = async (event) => {
    event.preventDefault();
    try {
      await axios.post('your-api-endpoint-here', { asuId, comment });
      setAsuId(''); // Clear ASU ID
      asuIdInputRef.current.focus(); // Focus back to ASU ID field
    } catch (error) {
      console.error('Error submitting the form:', error);
    }
  };
  return (
    <div className="max-w-md mx-auto bg-white p-6 rounded-lg shadow-md">
      <form onSubmit={handleSubmit}>
        <div className="mb-4">
          <label htmlFor="asuId" className="block text-gray-700 font-bold mb-2">
            ASU ID
          </label>
          <input
            id="asuId"
            type="text"
            value={asuId}
            onChange={(e) => setAsuId(e.target.value)}
            ref={asuIdInputRef}
            className="shadow appearance-none border rounded w-full py-2 px-3 text-gray-700 leading-tight focus:outline-none focus:shadow-outline"
            required
            autoFocus
          />
        </div>
        <div className="mb-4">
          <label htmlFor="comment" className="block text-gray-700 font-bold mb-2">
            Comment
          </label>
          <textarea
            id="comment"
            value={comment}
            onChange={(e) => setComment(e.target.value)}
            className="shadow appearance-none border rounded w-full py-2 px-3 text-gray-700 leading-tight focus:outline-none focus:shadow-outline"
            rows="4"
          />
        </div>
        <div className="flex items-center justify-between">
          <button
            type="submit"
            className="bg-blue-500 hover:bg-blue-700 text-white font-bold py-2 px-4 rounded focus:outline-none focus:shadow-outline"
          >
            Submit
          </button>
        </div>
      </form>
    </div>
  );
};
export default AddPoints;