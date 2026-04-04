import axios from "axios";

const apiClient = axios.create({
  baseURL: "/api",
  timeout: 30000,
  headers: {
    "Content-Type": "application/json",
  },
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
