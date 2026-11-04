# PersonAI Frontend - Setup & Integration Guide

## 📋 Project Overview

PersonAI is a modern ChatGPT-style frontend built with React + TypeScript + Vite that integrates with your existing Tamil Voice Assistant backend.

**Tech Stack:**
- React 19.3
- TypeScript
- Vite (fast dev server)
- Tailwind CSS (styling)
- Zustand (state management)
- Axios (HTTP client)
- React Markdown (message formatting)

---

## 🚀 Quick Start

### 1. Prerequisites

- Node.js 16+ ([download](https://nodejs.org/))
- npm or yarn
- Backend running on `localhost:8000` (your existing FastAPI server)

### 2. Install Dependencies

```bash
cd personai-frontend
npm install --legacy-peer-deps
```

### 3. Start Development Server

```bash
npm run dev
```

The frontend will be available at: `http://localhost:5173`

### 4. Open in Browser

Visit: http://localhost:5173

---

## 🔧 Configuration

### Backend URL

The frontend communicates with your backend via environment variables.

**File:** `.env`

```env
VITE_API_BASE_URL=http://localhost:8000
```

To change the backend URL:
1. Edit `.env`
2. Set `VITE_API_BASE_URL` to your backend address
3. Restart the dev server

---

## 📁 Project Structure

```
personai-frontend/
├── src/
│   ├── components/          # React components
│   │   ├── Sidebar.tsx
│   │   ├── ChatMessage.tsx
│   │   ├── MessageComposer.tsx
│   │   ├── VoiceVisualizer.tsx
│   │   └── WelcomeScreen.tsx
│   ├── pages/              # Page components
│   │   └── ChatPage.tsx
│   ├── services/           # API & service layer
│   │   ├── api.ts          # Backend API client
│   │   └── voiceService.ts # Voice recording & TTS
│   ├── store/              # State management (Zustand)
│   │   └── chatStore.ts
│   ├── types/              # TypeScript types
│   │   └── chat.ts
│   ├── App.tsx             # Root component
│   ├── main.tsx            # Entry point
│   └── index.css           # Global styles
├── .env                    # Environment variables
├── tailwind.config.js      # Tailwind configuration
├── postcss.config.js       # PostCSS configuration
├── vite.config.ts          # Vite configuration
└── package.json            # Dependencies
```

---

## 🔌 Backend Integration

### API Endpoints

The frontend connects to the following backend endpoints:

#### 1. Health Check
```
GET /api/health
Response: { "ollama": boolean, "whisper": boolean }
```

#### 2. Voice Turn (Speech-to-Text + LLM)
```
POST /api/voice-turn
Content-Type: multipart/form-data
Form Data: file (WAV blob)

Response: {
  "user_text": "transcribed text",
  "bot_text": "llm response",
  "stt_latency_ms": 1234,
  "llm_latency_ms": 5678
}
```

### Service Layer

All API calls go through the `ApiClient` class in `src/services/api.ts`:

```typescript
import { apiClient } from './services/api';

// Check backend health
const health = await apiClient.checkHealth();

// Send voice for processing
const response = await apiClient.voiceTurn(audioBlob);
```

---

## 🎙️ Voice Integration

### Voice Recording

The frontend uses the **Web Audio API** for voice recording:

```typescript
import { voiceService } from './services/voiceService';

// Start recording
await voiceService.startRecording();

// Stop and get WAV blob
const audioBlob = await voiceService.stopRecording();
```

Features:
- 16-bit PCM WAV encoding
- 16kHz sample rate
- Mono audio
- Direct browser capture (no codec dependencies)

### Text-to-Speech

The frontend uses the **Web Speech API** for TTS:

```typescript
// Play text as speech
await voiceService.playText('Hello, how are you?', 0.7);

// Stop playback
voiceService.stopPlayback();
```

Configuration:
- Language: Tamil (ta-IN) with fallback to English
- Speech rate: 0.7x (adjustable)
- Pitch: 1.0 (normal)
- Volume: 1.0 (max)

---

## 💾 State Management

The app uses **Zustand** for simple, lightweight state management.

### Chat Store

Located in `src/store/chatStore.ts`:

```typescript
import { useChatStore } from './store/chatStore';

// Use the store
const { conversations, currentConversationId, addMessage } = useChatStore();

// Create new conversation
useChatStore.getState().createConversation();

// Add message
useChatStore.getState().addMessage({
  id: '1',
  role: 'user',
  content: 'Hello',
  timestamp: new Date(),
});
```

---

## 🎨 Design System

The frontend uses **Tailwind CSS** with a custom dark theme:

### Color Palette

```css
--dark-bg: #0f0f1e          /* Main background */
--dark-card: #1a1a2e        /* Card background */
--dark-border: #2d2d44      /* Border color */
--dark-text: #e0e0e0        /* Primary text */
--dark-text-muted: #9ca3af  /* Secondary text */
--accent-purple: #a78bfa    /* Primary accent */
--accent-purple-dark: #7c3aed  /* Darker accent */
--accent-purple-light: #c4b5fd /* Lighter accent */
```

### Typography

- **Font:** Inter (Google Fonts)
- **Display:** Bold 5xl-6xl
- **Heading:** Bold lg-2xl
- **Body:** Regular 14px-16px
- **Caption:** Muted 12px-14px

---

## 📦 Build for Production

```bash
npm run build
```

Output: `dist/` directory (ready to deploy)

Preview the build:
```bash
npm run preview
```

---

## 🧪 Testing the Integration

### 1. Check Backend Health

```bash
curl http://localhost:8000/api/health
```

Expected response:
```json
{"ollama": true, "whisper": true}
```

### 2. Test Voice Processing

1. Click the microphone button
2. Speak in Tamil (e.g., "வணக்கம்")
3. Listen for the response audio
4. Check transcription and latency metrics

### 3. Test Text Input

1. Type a message in the text box
2. Press Enter or click Send
3. Message should appear in chat

---

## 🐛 Troubleshooting

### Frontend won't start

**Error:** `npm ERR! code ERESOLVE`

**Solution:**
```bash
npm install --legacy-peer-deps
npm run dev
```

### Can't connect to backend

**Error:** "Request timeout" or "Backend service unavailable"

**Check:**
1. Backend is running: `python server.py`
2. Backend URL in `.env` is correct
3. Both backend and frontend are on same machine/network
4. Ollama service is running: `ollama serve`

### Microphone permission denied

**Solution:**
1. Allow microphone access when prompted
2. Check browser permissions in settings
3. Some browsers require HTTPS (use localhost for development)

### Voice input not working

**Check:**
1. Browser supports Web Audio API (Chrome, Firefox, Safari, Edge)
2. Microphone is connected and working
3. Wear headphones to avoid acoustic feedback
4. Speak clearly and loudly

### Text messages not sending

**Check:**
1. Message text is not empty
2. Backend is responding to requests
3. Check browser console for errors

---

## 🔐 Security Notes

- No API keys are hardcoded
- All backend communication goes through environment variables
- Voice data is sent as binary WAV blobs
- No personal data is stored locally (except conversation history in memory)
- CORS is enabled on backend for local development

**For production:**
- Deploy frontend and backend separately
- Use HTTPS
- Configure CORS properly
- Implement proper authentication
- Add rate limiting on backend

---

## 📱 Responsive Design

The frontend is fully responsive:

- **Mobile:** Single column, collapsible sidebar
- **Tablet:** 600px-1024px breakpoints
- **Desktop:** Full layout with visible sidebar

Test on different screen sizes:
```bash
npm run dev
# Open DevTools (F12) and use device emulation
```

---

## 🚀 Next Steps

### Features to Add Later

1. **Text Input Support**
   - Implement text-to-speech for text-based LLM
   - Add streaming responses

2. **Conversation Persistence**
   - Save conversations to backend
   - Load conversation history from database

3. **User Authentication**
   - Login/signup system
   - User profiles and preferences

4. **Advanced Features**
   - Conversation search
   - Export conversations
   - Settings/preferences UI
   - Dark/light theme toggle
   - Language selection (Tamil/English)

5. **Mobile App**
   - React Native version
   - Native voice integration
   - Offline support

---

## 📚 Resources

- [React Documentation](https://react.dev)
- [TypeScript Handbook](https://www.typescriptlang.org/docs/)
- [Tailwind CSS](https://tailwindcss.com/docs)
- [Zustand](https://github.com/pmndrs/zustand)
- [Vite Documentation](https://vite.dev/)
- [Web Audio API](https://developer.mozilla.org/en-US/docs/Web/API/Web_Audio_API)
- [Web Speech API](https://developer.mozilla.org/en-US/docs/Web/API/Web_Speech_API)

---

## 📞 Support

For issues or questions:

1. Check the troubleshooting section
2. Review browser console for errors
3. Ensure backend is running and healthy
4. Check backend logs for API errors

---

**Frontend Version:** 1.0.0  
**Last Updated:** November 2026  
**Backend Compatibility:** Tamil Voice Assistant (FastAPI)
