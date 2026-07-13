# DASH - Project Context

## Goal

DASH is a production-grade personal AI assistant that runs on both Windows and Android.

It acts as my intelligent assistant, can communicate with me naturally, automate tasks, and control my laptop (with appropriate confirmations for sensitive actions).

The mobile app connects securely to my laptop through a backend so I can control DASH remotely.

## Core Features

- Conversational AI
- Voice input and output
- Internet search
- Coding assistant
- File management
- Email management
- Calendar
- Browser automation
- Desktop automation
- Notifications
- Long-term memory
- Plugin system
- Workflow automation
- Remote control from mobile

## Technology

Backend:
- Python
- FastAPI
- PostgreSQL
- Redis
- SQLAlchemy
- WebSockets

Desktop:
- Electron
- React
- TypeScript

Mobile:
- Flutter

Automation:
- Playwright

AI:
- Provider-agnostic (OpenAI-compatible APIs and local models such as Ollama)

## Architecture

Android App
        ↓
FastAPI Backend
        ↓
Desktop Agent
        ↓
Windows APIs, Browser, Files, Email, Terminal

## Requirements

- Production quality
- Modular architecture
- Docker support
- Secure
- Testable
- Cross-platform where practical
- Type-safe
- Environment variables only
- No hardcoded secrets

## Coding Rules

- Never break existing code.
- Never delete unrelated files.
- Follow existing architecture.
- Keep modules independent.
- Generate tests when appropriate.
- Write clean documentation.