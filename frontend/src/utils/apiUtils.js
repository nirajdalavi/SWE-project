// frontend/src/utils/apiUtils.js

/**
 * Get the appropriate backend URL based on environment
 * @param {string} path - The API path (e.g., '/pdf/workspace/file.pdf')
 * @returns {string} - The complete URL
 */
export const getBackendUrl = (path = '') => {
  const backendHost = process.env.REACT_APP_BACKEND_HOST || 'localhost';
  
  if (backendHost === 'localhost') {
    // Local development
    return `http://${backendHost}:8000${path}`;
  } else {
    // Production - handle both cases where backendHost includes protocol or not
    if (backendHost.startsWith('http')) {
      // If it already includes protocol, add /api prefix
      return `${backendHost}/api${path}`;
    } else {
      return `https://${backendHost}/api${path}`;
    }
  }
};

/**
 * Get the backend base URL without path
 * @returns {string} - The base URL
 */
export const getBackendBaseUrl = () => {
  const backendHost = process.env.REACT_APP_BACKEND_HOST || 'localhost';
  
  if (backendHost === 'localhost') {
    return `http://${backendHost}:8000`;
  } else {
    // Production - handle both cases where backendHost includes protocol or not
    if (backendHost.startsWith('http')) {
      // If it already includes protocol, add /api prefix
      return `${backendHost}/api`;
    } else {
      return `https://${backendHost}/api`;
    }
  }
};
