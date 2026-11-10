import axios from 'axios';
import type { AxiosInstance } from 'axios';
import type { VoiceResponseData, HealthStatus } from '../types/chat';
import { API_BASE } from '../constants';

class ApiClient {
  private client: AxiosInstance;

  constructor() {
    this.client = axios.create({
      baseURL: API_BASE,
      timeout: 120000,
      headers: {
        'Content-Type': 'application/json',
      },
    });

    // Add request interceptor for error handling
    this.client.interceptors.response.use(
      response => response,
      error => {
        if (error.code === 'ECONNABORTED') {
          return Promise.reject(new Error('Request timeout. Please check if the backend is running.'));
        }
        if (error.response?.status === 503) {
          return Promise.reject(new Error('Backend service unavailable. Ensure Ollama is running.'));
        }
        return Promise.reject(error);
      }
    );
  }

  // Health check
  async checkHealth(): Promise<HealthStatus> {
    try {
      const response = await this.client.get('/health');
      return response.data;
    } catch (error) {
      console.error('Health check failed:', error);
      return { ollama: false, whisper: false };
    }
  }

  // Voice turn - send audio and get response
  async voiceTurn(audioBlob: Blob): Promise<VoiceResponseData> {
    try {
      const formData = new FormData();
      formData.append('file', audioBlob, 'audio.wav');

      const response = await this.client.post<VoiceResponseData>(
        '/voice-turn',
        formData,
        {
          headers: {
            'Content-Type': 'multipart/form-data',
          },
        }
      );

      return response.data;
    } catch (error) {
      console.error('Voice turn error:', error);
      throw error;
    }
  }

  // Get backend URL for reference
  getBaseURL(): string {
    return API_BASE;
  }
}

export const apiClient = new ApiClient();
