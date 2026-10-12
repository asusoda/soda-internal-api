import axios from "axios";
import config from "../../config";

// Calls of the member store. The API keeps the member's Discord sign-in in its session cookie, so each
// request sends cookies. The officer token is not sent.
const memberClient = axios.create({
  baseURL: config.apiUrl,
  withCredentials: true,
});

// Starts the member's Discord sign-in. The API returns the browser to /store/<orgPrefix>.
export const storeLoginUrl = (orgPrefix: string) =>
  `${config.apiUrl}/api/auth/store_login?org=${encodeURIComponent(orgPrefix)}`;

export default memberClient;
