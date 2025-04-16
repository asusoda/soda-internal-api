import axios from 'axios';
import { useEffect, useState } from 'react';
import { useCookies } from 'react-cookie';

const useRequestManager = (endpoint, requestType, requestData = {}) => {
    const [response, setResponse] = useState(null);
    const [error, setError] = useState(null);
    const [cookies, setCookie, removeCookie] = useCookies(['accessToken']);

    const makeRequest = async () => {
        try {
            const token = cookies.accessToken;
            const headers = { Authorization: `Bearer ${token}` };
            let res;

            switch (requestType.toLowerCase()) {
                case 'get':
                    res = await axios.get(endpoint, { headers });
                    break;
                case 'post':
                    res = await axios.post(endpoint, requestData, { headers });
                    break;
                case 'put':
                    res = await axios.put(endpoint, requestData, { headers });
                    break;
                case 'delete':
                    res = await axios.delete(endpoint, { headers });
                    break;
                default:
                    throw new Error('Invalid request type');
            }

            setResponse(res.data);
        } catch (err) {
            if (err.response && err.response.status === 401) {
                await refreshToken();
            } else {
                setError(err);
            }
        }
    };

    const refreshToken = async () => {
        try {
            const res = await axios.post('/auth/requestToken', { token: cookies.accessToken });
            if (res.status === 200) {
                setCookie('accessToken', res.data.accessToken, { path: '/' });
                makeRequest(); // Retry original request with new token
            } else {
                throw new Error('Token renewal failed');
            }
        } catch (err) {
            removeCookie('accessToken');
            setError(err);
        }
    };

    useEffect(() => {
        if (cookies.accessToken) {
            makeRequest();
        }
    }, [endpoint, requestType, requestData]);

    return { response, error };
};

export default useRequestManager;