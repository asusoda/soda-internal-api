import axios from 'axios';

const API_BASE_URL = process.env.REACT_APP_API_BASE_URL;

export const getName = async() => {
  try {
    const response = await axios.get(`${API_BASE_URL}/auth/name`,{
      headers: {
        'Authorization': `${localStorage.getItem('token')}`
      }
  });
    return response.data;
  } catch (error) {
    console.error("Error fetching name", error);
    throw error;
  }
}

export const getLeaderboard = async () => {
  try {
    const response = await axios.get(`${API_BASE_URL}/points/leaderboard`);
    return response.data;
  } catch (error) {
    console.error("Error fetching leaderboard", error);
    throw error;
  }
};

export const addPoints = async (userId, eventName, points) => {
  try {
    const response = await axios.post(`${API_BASE_URL}/add-points`, {
      user_id: userId,
      event: eventName,
      points: points
    });
    return response.data;
  } catch (error) {
    console.error("Error adding points", error);
    throw error;
  }
};

export const removePoints = async (userId, points) => {
  try {
    const response = await axios.post(`${API_BASE_URL}/remove-points`, {
      user_id: userId,
      points: points
    });
    return response.data;
  } catch (error) {
    console.error("Error removing points", error);
    throw error;
  }
};
