import React, { useState, useRef, useEffect } from 'react';

const InlineEdit = ({ 
  value, 
  onSave, 
  onCancel, 
  placeholder = "Enter value...",
  className = "",
  maxLength = 20,
  validation = null // Function that returns error message or null
}) => {
  const [isEditing, setIsEditing] = useState(false);
  const [inputValue, setInputValue] = useState(value);
  const [error, setError] = useState(null);
  const inputRef = useRef(null);

  useEffect(() => {
    if (isEditing && inputRef.current) {
      inputRef.current.focus();
      inputRef.current.select();
    }
  }, [isEditing]);

  const handleEdit = () => {
    setIsEditing(true);
    setInputValue(value);
    setError(null);
  };

  const handleSave = async () => {
    // Validate input
    if (validation) {
      const validationError = validation(inputValue);
      if (validationError) {
        setError(validationError);
        return;
      }
    }

    try {
      await onSave(inputValue);
      setIsEditing(false);
      setError(null);
    } catch (error) {
      setError(error.message || 'Failed to save');
    }
  };

  const handleCancel = () => {
    setIsEditing(false);
    setInputValue(value);
    setError(null);
    if (onCancel) onCancel();
  };

  const handleKeyDown = (e) => {
    if (e.key === 'Enter') {
      handleSave();
    } else if (e.key === 'Escape') {
      handleCancel();
    }
  };

  if (isEditing) {
    return (
      <div className={`inline-block ${className}`}>
        <input
          ref={inputRef}
          type="text"
          value={inputValue}
          onChange={(e) => setInputValue(e.target.value)}
          onKeyDown={handleKeyDown}
          onBlur={handleSave}
          placeholder={placeholder}
          maxLength={maxLength}
          className="bg-gray-700/50 border border-blue-500/50 rounded px-2 py-1 text-white focus:outline-none focus:ring-2 focus:ring-blue-500 min-w-0"
        />
        {error && (
          <div className="text-red-400 text-xs mt-1">{error}</div>
        )}
      </div>
    );
  }

  return (
    <div className={`inline-flex items-center space-x-1 ${className}`}>
      <span 
        onClick={handleEdit}
        className="cursor-pointer hover:text-blue-300 transition-colors"
        title="Click to edit"
      >
        {value}
      </span>
      <svg 
        onClick={handleEdit}
        className="w-3 h-3 text-gray-400 hover:text-blue-300 cursor-pointer transition-colors" 
        fill="none" 
        stroke="currentColor" 
        viewBox="0 0 24 24"
        title="Click to edit"
      >
        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M11 5H6a2 2 0 00-2 2v11a2 2 0 002 2h11a2 2 0 002-2v-5m-1.414-9.414a2 2 0 112.828 2.828L11.828 15H9v-2.828l8.586-8.586z" />
      </svg>
    </div>
  );
};

export default InlineEdit;
