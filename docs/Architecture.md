# DASH Architecture Overview

## Project Structure
```
dash/
├── apps/
│   └── desktop/                 # Electron Desktop Application
│       ├── electron/           # Electron main & preload processes
│       │   ├── main.ts         # Main process entry point
│       │   └── preload.ts      # Secure IPC bridge
│       ├── src/
│       │   ├── components/     # Reusable React components
│       │   ├── pages/          # Page components (Dashboard, Chat, Settings, etc.)
│       │   ├── stores/        # Zustand state management
│       │   ├── types/         # TypeScript type definitions
│       │   └── App.tsx        # Main app with routing
│       └── package.json       # Desktop app dependencies
├── dash_backend/               # Backend AI infrastructure
│   ├── src/
│   │   ├── modules/           # Feature modules
│   │   │   ├── core/         # Core system services
│   │   │   ├── auth/         # Authentication & authorization
│   │   │   ├── api/          # REST API endpoints
│   │   │   ├── websocket/    # Real-time communication
│   │   │   └── database/     # Database connections & migrations
│   │   └── main.ts           # Backend entry point
│   └── services/              # AI & external services
│       ├── ai/
│       │   ├── providers/    # LLM providers
│       │   │   ├── anthropic/    # Claude models
│       │   │   ├── openai/       # GPT models
│       │   │   ├── gemini/       # Google Gemini
│       │   │   ├── openrouter/   # OpenRouter aggregation
│       │   │   └── local/        # Local model support
│       │   ├── agents/       # AI agents
│       │   │   ├── executor/     # Task execution
│       │   │   ├── planner/      # Task planning
│       │   │   └── code/         # Code generation
│       │   └── tools/         # Tool integrations
│       ├── storage/          # File & cloud storage
│       └── search/           # Vector search & RAG
└── docs/
    ├── ARCHITECTURE.md        # This document
    └── ROADMAP.md             # Development roadmap
```

## Desktop Application (Electron + React)

### Electron Architecture
- **Main Process (`main.ts`)**: Manages window lifecycle, auto-updater, system integration
- **Preload Script (`preload.ts`)**: Secure IPC bridge exposing limited APIs to renderer
- **Auto-updater Integration**: Built-in `electron-updater` with GitHub release support
- **IPC Communication**: Type-safe channel-based messaging between main and renderer

### Frontend Architecture
- **React 19 + TypeScript**: Modern React with full type safety
- **React Router v7**: Client-side routing with protected layouts
- **Zustand**: Lightweight state management for auth and app state
- **Framer Motion**: Smooth animations and transitions
- **Tailwind CSS**: Utility-first styling with glass-morphism design
- **Lucide React**: Consistent icon library

### Core Frontend Pages
- `/` - Dashboard: Main overview and statistics
- `/chat` - Chat Interface: AI conversation with history
- `/memory` - Memory Management: Store and retrieve past interactions
- `/projects` - Project workspace: Manage AI projects
- `/automation` - Automation Hub: Create and run automations
- `/settings` - Settings: App configuration including software updates

## Backend Architecture

### Module Structure
- **Core**: Foundation services, configuration, logging
- **Auth**: User authentication, JWT tokens, session management
- **API**: RESTful API endpoints with Express/FastAPI
- **WebSocket**: Real-time bidirectional communication
- **Database**: ORM setup, migrations, connections (PostgreSQL + Redis)

### AI Services Layer
- **Providers**: Abstract layer for multiple LLM providers with unified interface
- **Agents**: Autonomous AI agents that can plan and execute tasks
- **Tools**: Integrations with external APIs, file systems, and services
- **RAG**: Retrieval-augmented generation with vector search (Pinecone/Chroma)

### Scalability Features
- Modular monolith architecture that can transition to microservices
- Async task queue for background processing
- Horizontal scaling support for AI workloads
- Caching layer for frequent LLM responses

## Auto-Updater Implementation

### Main Process (electron/main.ts)
```typescript
- Sends update events via IPC to renderer
- Handles check-for-updates, start-download, quit-and-install IPC calls
- Configurable auto-download and auto-install-on-exit settings
- Events: checking-for-update, update-available, download-progress, update-downloaded, error
```

### Renderer Process
- **Settings.tsx**: User preferences persist to localStorage
- **UpdateModal.tsx**: Real-time update status and user interactions
- **electron.d.ts**: TypeScript definitions for `window.dash` API
- All updater events properly received and handled in UI

## Security Model
- Electron context isolation enabled
- Limited IPC exposure through preload script
- CSP headers for frontend security
- Input validation on all API endpoints
- Secure LLM provider API key storage

## Build & Deployment
- Vite for fast frontend development and builds
- Electron Builder for desktop packaging (NSIS installer for Windows)
- CI/CD ready for automated builds and releases
- GitHub releases integration for auto-updates
```