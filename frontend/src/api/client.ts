import axios from "axios";

const apiClient = axios.create({
  baseURL: import.meta.env.VITE_API_URL || "/api",
  timeout: 120000,
  headers: {
    "Content-Type": "application/json",
  },
});

// Attach JWT token to every request
apiClient.interceptors.request.use((config) => {
  const token = localStorage.getItem("stockdash_token");
  if (token) {
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});

apiClient.interceptors.response.use(
  (response) => response,
  (error) => {
    if (error.response) {
      const { status, data } = error.response;
      console.error(`API Error [${status}]:`, data?.detail || data?.message || "Unknown error");
    } else if (error.request) {
      console.error("API Error: No response received", error.message);
    } else {
      console.error("API Error:", error.message);
    }
    return Promise.reject(error);
  },
);

export default apiClient;
