# Chief of Staff AI - Multi-Agent Executive Assistant

An industry-grade AI-powered executive assistant featuring multi-agent orchestration, RAG capabilities, and a stunning modern UI.

## Features

- **Multi-Agent Architecture**: Master orchestrator with specialized worker agents
  - Calendar Manager - Schedule meetings, manage appointments
  - Email Manager - Draft, summarize, and prioritize communications
  - Research Analyst - Conduct research and provide insights
  - Task Manager - Track projects, deadlines, and priorities
  - Analytics Expert - Data analysis and business intelligence

- **Advanced Memory System**: Each agent maintains its own memory using LangChain
  - Short-term conversation memory
  - Long-term vector-based semantic memory
  - Cross-conversation context preservation

- **RAG (Retrieval Augmented Generation)**: Upload documents and get AI-powered answers
  - Supports PDF, DOCX, TXT, MD, XLSX, CSV
  - pgvector for efficient similarity search
  - Automatic document chunking and embedding

- **Beautiful Modern UI**: Eye-catching React/Next.js interface
  - Glass morphism design
  - Smooth animations with Framer Motion
  - Real-time agent status indicators
  - Dark mode optimized

## Tech Stack

- **Backend**: Python, Flask, LangGraph, LangChain
- **Frontend**: Next.js 14, React, TypeScript, Tailwind CSS
- **Database**: PostgreSQL with pgvector extension
- **LLM**: OpenAI GPT-4o-mini
- **Caching**: Redis
- **Deployment**: Docker & Docker Compose

## Quick Start

### Prerequisites

- Docker & Docker Compose
- OpenAI API Key

### Installation

1. Clone the repository:
```bash
cd /Users/sarangmehta/Desktop/agentic-chief-of-staff
```

2. Create environment file:
```bash
cp .env.example .env
```

3. Add your OpenAI API key to `.env`:
```
OPENAI_API_KEY=your-api-key-here
```

4. Start the services:
```bash
docker-compose up -d --build
```

5. Access the application:
- Frontend: http://localhost:3001
- Backend API: http://localhost:9001
- PgAdmin: http://localhost:5052

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                        Frontend                              │
│                   (Next.js + React)                          │
└─────────────────────────┬───────────────────────────────────┘
                          │
                          ▼
┌─────────────────────────────────────────────────────────────┐
│                    Flask API Server                          │
│              (REST + WebSocket endpoints)                    │
└─────────────────────────┬───────────────────────────────────┘
                          │
                          ▼
┌─────────────────────────────────────────────────────────────┐
│                  LangGraph Orchestrator                      │
│                                                              │
│  ┌──────────────┐                                           │
│  │   Master     │                                           │
│  │ Orchestrator │                                           │
│  └──────┬───────┘                                           │
│         │                                                    │
│         ▼                                                    │
│  ┌──────────────────────────────────────────────────────┐   │
│  │              Specialized Agents                       │   │
│  │  ┌────────┐ ┌────────┐ ┌────────┐ ┌────────┐ ┌─────┐│   │
│  │  │Calendar│ │ Email  │ │Research│ │  Task  │ │Data ││   │
│  │  │ Agent  │ │ Agent  │ │ Agent  │ │ Agent  │ │Agent││   │
│  │  └────────┘ └────────┘ └────────┘ └────────┘ └─────┘│   │
│  └──────────────────────────────────────────────────────┘   │
└─────────────────────────┬───────────────────────────────────┘
                          │
          ┌───────────────┼───────────────┐
          ▼               ▼               ▼
   ┌────────────┐  ┌────────────┐  ┌────────────┐
   │ PostgreSQL │  │   Redis    │  │  OpenAI    │
   │ + pgvector │  │   Cache    │  │    API     │
   └────────────┘  └────────────┘  └────────────┘
```

## API Endpoints

### Chat
- `POST /api/chat/message` - Send a message
- `POST /api/chat/stream` - Stream a response (SSE)

### Conversations
- `GET /api/conversations` - List conversations
- `GET /api/conversations/:id` - Get conversation details
- `POST /api/conversations` - Create new conversation
- `DELETE /api/conversations/:id` - Delete conversation

### Agents
- `GET /api/agents` - List all agents
- `GET /api/agents/:id` - Get agent details
- `GET /api/agents/:id/memories` - Get agent memories

### Documents
- `GET /api/documents` - List uploaded documents
- `POST /api/documents` - Upload a document
- `POST /api/documents/search` - Search documents (RAG)

## Configuration

### Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `OPENAI_API_KEY` | OpenAI API key | Required |
| `POSTGRES_USER` | Database user | cos_user |
| `POSTGRES_PASSWORD` | Database password | cos_secure_pass_2024 |
| `POSTGRES_DB` | Database name | chief_of_staff |
| `REDIS_URL` | Redis connection URL | redis://redis:6379/0 |
| `FLASK_ENV` | Flask environment | production |

## Development

### Backend Development
```bash
cd backend
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
python -m app.main
```

### Frontend Development
```bash
cd frontend
npm install
npm run dev
```

## Ports Used

| Service | Port |
|---------|------|
| Frontend | 3001 |
| Backend API | 9001 |
| PostgreSQL | 5442 |
| Redis | 6380 |
| PgAdmin | 5052 |

## License

MIT License
