/**
 * API client for TAMIL-LLM backend.
 * Handles all HTTP communication with the FastAPI backend.
 */

const API_BASE_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000'

/**
 * Send a message to the chatbot and get a response.
 * @param {string} message - User message
 * @returns {Promise<{reply: string, language: string, extracted_facts: Array}>}
 */
export async function sendMessage(message) {
  if (!message.trim()) {
    throw new Error('Message cannot be empty')
  }

  try {
    const response = await fetch(`${API_BASE_URL}/api/chat`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({ message: message.trim() }),
    })

    if (!response.ok) {
      const errorData = await response.json().catch(() => ({}))
      throw new Error(errorData.detail || errorData.error || `HTTP ${response.status}`)
    }

    return await response.json()
  } catch (error) {
    throw new Error(`Failed to send message: ${error.message}`)
  }
}

/**
 * Get health status of the backend.
 * @returns {Promise<{status: string, ollama_ready: boolean, model: string}>}
 */
export async function checkHealth() {
  try {
    const response = await fetch(`${API_BASE_URL}/health`)
    if (!response.ok) {
      throw new Error(`HTTP ${response.status}`)
    }
    return await response.json()
  } catch (error) {
    throw new Error(`Backend unavailable: ${error.message}`)
  }
}

/**
 * Get all stored memories from the database.
 * @returns {Promise<Array<{key: string, value: string, category: string, ...}>>}
 */
export async function getMemories() {
  try {
    const response = await fetch(`${API_BASE_URL}/api/memories`)
    if (!response.ok) {
      throw new Error(`HTTP ${response.status}`)
    }
    return await response.json()
  } catch (error) {
    throw new Error(`Failed to fetch memories: ${error.message}`)
  }
}
