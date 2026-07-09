import axios from "axios";

const client = axios.create({
  baseURL: import.meta.env.VITE_API_URL ?? "",
  timeout: 30000,
});

// Attach JWT from localStorage automatically
client.interceptors.request.use((config) => {
  const token = localStorage.getItem("access_token");
  if (token) config.headers.Authorization = `Bearer ${token}`;
  return config;
});

// Redirect to login on 401 (debounced — only once if multiple requests fail)
let _redirecting = false;
client.interceptors.response.use(
  (res) => res,
  (err) => {
    if (err.response?.status === 401 && !_redirecting) {
      _redirecting = true;
      localStorage.removeItem("access_token");
      window.location.href = "/login";
    }
    return Promise.reject(err);
  }
);

export default client;
