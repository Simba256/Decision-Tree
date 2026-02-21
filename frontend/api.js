/**
 * API Client for Career Decision Tree Backend
 * All API calls go through here
 */

const API_BASE_URL = 'http://localhost:5000/api';

/**
 * Fetch all programs with optional filters
 * @param {Object} filters - Query parameters for filtering
 * @returns {Promise<Array>} Array of program objects
 */
export async function fetchPrograms(filters = {}) {
  const params = new URLSearchParams(filters);
  const url = `${API_BASE_URL}/programs?${params}`;

  const response = await fetch(url);
  if (!response.ok) {
    throw new Error(`API error: ${response.status}`);
  }

  const data = await response.json();
  return data.programs;
}

/**
 * Fetch a single program by ID
 * @param {number} id - Program ID
 * @returns {Promise<Object>} Program object
 */
export async function fetchProgram(id) {
  const response = await fetch(`${API_BASE_URL}/programs/${id}`);
  if (!response.ok) {
    throw new Error(`API error: ${response.status}`);
  }

  return response.json();
}

/**
 * Fetch all universities
 * @returns {Promise<Array>} Array of university objects
 */
export async function fetchUniversities() {
  const response = await fetch(`${API_BASE_URL}/universities`);
  if (!response.ok) {
    throw new Error(`API error: ${response.status}`);
  }

  const data = await response.json();
  return data.universities;
}

/**
 * Fetch summary statistics
 * @returns {Promise<Object>} Stats object
 */
export async function fetchStats() {
  const response = await fetch(`${API_BASE_URL}/stats`);
  if (!response.ok) {
    throw new Error(`API error: ${response.status}`);
  }

  return response.json();
}

/**
 * Search programs by keyword
 * @param {string} query - Search query
 * @returns {Promise<Array>} Array of matching programs
 */
export async function searchPrograms(query) {
  const response = await fetch(`${API_BASE_URL}/search?q=${encodeURIComponent(query)}`);
  if (!response.ok) {
    throw new Error(`API error: ${response.status}`);
  }

  const data = await response.json();
  return data.results;
}

/**
 * Check if API is healthy
 * @returns {Promise<boolean>} True if API is healthy
 */
export async function checkHealth() {
  try {
    const response = await fetch(`${API_BASE_URL}/health`);
    if (!response.ok) return false;

    const data = await response.json();
    return data.status === 'ok';
  } catch (error) {
    return false;
  }
}
