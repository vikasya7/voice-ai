# AI Voice Receptionist

An AI-powered voice receptionist that automates customer conversations, appointment management and business communication through natural voice interactions.

Built using **Python, FastAPI, LangGraph, PostgreSQL, Twilio and OpenAI**, the system can understand customer requests, manage appointment workflows, integrate with Google Calendar and send email confirmations.

## Overview

Small businesses often spend significant time answering repetitive customer calls, managing appointments and responding to enquiries.

AI Voice Receptionist aims to automate these operations through an intelligent conversational agent that can communicate with customers over phone calls.

The agent uses speech processing and LLM-powered intent classification to understand customer requests and route them through appropriate workflows.

## Key Features

### 1. AI-Powered Voice Conversations
- Handles customer conversations through phone calls.
- Converts incoming audio into text using speech-to-text.
- Uses an LLM to understand customer intent.
- Generates natural responses using text-to-speech.
- Maintains conversation context across multiple interactions.

### 2. Appointment Booking
- Collects customer information, service details, date and time.
- Checks appointment availability.
- Prevents conflicting bookings.
- Stores appointments in PostgreSQL.
- Creates corresponding Google Calendar events.
- Sends booking confirmation emails through Gmail.

### 3. Appointment Cancellation
- Identifies customers using their registered phone number.
- Retrieves existing confirmed appointments.
- Handles multiple appointments by asking customers to select the correct one.
- Requests customer confirmation before cancellation.
- Deletes the corresponding Google Calendar event.
- Updates appointment status in PostgreSQL.

### 4. Google Calendar Integration
- Checks calendar availability.
- Creates appointment events.
- Deletes calendar events when appointments are cancelled.
- Synchronizes booking operations with Google Calendar.

### 5. Email Notifications
- Sends appointment confirmation emails.
- Uses Gmail API for email delivery.
- Keeps email failures isolated from successful appointment creation.

### 6. Conversation State Management
- Uses LangGraph to orchestrate conversational workflows.
- Maintains session-specific conversation state.
- Routes conversations based on customer intent.
- Supports multi-step interactions such as collecting missing booking details and confirming cancellations.

## Technology Stack

| Category | Technologies |
|---|---|
| Language | Python |
| Backend | FastAPI |
| AI Orchestration | LangGraph, LangChain |
| LLM | OpenAI |
| Database | PostgreSQL |
| ORM | SQLAlchemy |
| Database Migrations | Alembic |
| Telephony | Twilio |
| Speech Processing | Speech-to-Text, Text-to-Speech |
| Calendar | Google Calendar API |
| Email | Gmail API |
| State Persistence | LangGraph Checkpointer, SQLite |

## System Architecture

```text
                 Customer
                    |
                    v
               Phone Call
                    |
                    v
                  Twilio
                    |
                    v
             FastAPI Backend
                    |
                    v
          Speech-to-Text (STT)
                    |
                    v
             LangGraph Agent
                    |
                    v
             Intent Detection
                    |
          +---------+----------+
          |         |          |
          v         v          v
       Booking   Cancellation  FAQ
          |         |          |
          v         v          v
      Availability Appointment Business
         Check    Lookup       Knowledge
          |         |          |
          +---------+----------+
                    |
                    v
             External Services
              /            \
             v              v
       Google Calendar    Gmail API
             |
             v
          PostgreSQL
                    |
                    v
             Response Generation
                    |
                    v
               Text-to-Speech
                    |
                    v
                Twilio
                    |
                    v
                 Customer
```

## Project Structure

```text
voice-agent/
│
├── alembic/
│   └── migrations/
│
├── app/
│   ├── agent/
│   │   ├── assistant.py
│   │   ├── assistant_tools.py
│   │   ├── graph.py
│   │   ├── nodes.py
│   │   ├── state.py
│   │   └── tools.py
│   │
│   ├── database/
│   │   ├── database.py
│   │   └── models.py
│   │
│   ├── services/
│   │   ├── calendar_service.py
│   │   └── email_service.py
│   │
│   ├── voice/
│   │   ├── audio.py
│   │   ├── normalization.py
│   │   ├── stt.py
│   │   └── tts.py
│   │
│   ├── rag/
│   │   └── knowledge.py
│   │
│   └── main.py
│
├── tests/
│
├── google_auth.py
├── alembic.ini
├── requirements.txt
├── .env
├── .gitignore
└── README.md
```

## Getting Started

### Prerequisites

Make sure you have the following installed:

- Python 3.10+
- PostgreSQL
- Git
- A Twilio account
- An OpenAI API key
- A Google Cloud project with Calendar API and Gmail API enabled

### 1. Clone the Repository

```bash
git clone <YOUR_REPOSITORY_URL>
cd voice-agent
```

### 2. Create a Virtual Environment

```bash
python -m venv venv
```

Activate it:

**macOS / Linux**

```bash
source venv/bin/activate
```

**Windows**

```bash
venv\Scripts\activate
```

### 3. Install Dependencies

```bash
pip install -r requirements.txt
```

### 4. Configure Environment Variables

Create a `.env` file in the project root.

Add your required configuration:

```env
OPENAI_API_KEY=your_openai_api_key

DATABASE_URL=postgresql://username:password@localhost:5432/voice_agent

TWILIO_ACCOUNT_SID=your_twilio_account_sid
TWILIO_AUTH_TOKEN=your_twilio_auth_token
TWILIO_PHONE_NUMBER=your_twilio_phone_number
```

Add any additional environment variables required by your implementation.

**Important:** Never commit API keys, credentials or sensitive configuration files to GitHub.

### 5. Configure Google OAuth

1. Create a project in Google Cloud Console.
2. Enable Google Calendar API.
3. Enable Gmail API.
4. Configure OAuth consent and create OAuth credentials.
5. Download the OAuth client credentials.
6. Place the credentials file in the location expected by `google_auth.py`.
7. Run the authentication flow to generate your token.

Keep `credentials.json` and `token.json` private. Never upload them to a public repository.

### 6. Configure the Database

Make sure PostgreSQL is running and your database exists.

Apply database migrations:

```bash
alembic upgrade head
```

### 7. Run the Application

Start the FastAPI server using your configured application entry point:

```bash
uvicorn app.main:app --reload
```

Open the interactive API documentation:

```text
http://127.0.0.1:8000/docs
```

Use Swagger UI to test the available API endpoints.

### 8. Configure Twilio

To connect phone calls to your FastAPI application:

1. Configure your Twilio phone number.
2. Expose your local server through a public HTTPS tunnel during development.
3. Configure the relevant Twilio webhook or Media Streams endpoint.
4. Start your application and test a phone call.

Make sure the webhook paths and connection settings match your actual FastAPI implementation.

## Appointment Workflow

### Booking Flow

```text
Customer Request
      |
      v
Intent Classification
      |
      v
Extract Appointment Details
      |
      v
Check Availability
      |
      v
Collect Missing Information
      |
      v
Customer Confirmation
      |
      v
Create Database Appointment
      |
      v
Create Google Calendar Event
      |
      v
Send Confirmation Email
      |
      v
Booking Completed
```

### Cancellation Flow

```text
Customer Requests Cancellation
             |
             v
     Identify Customer
             |
             v
     Retrieve Appointments
             |
             v
    Multiple Appointments?
          /       \
        Yes        No
         |          |
         v          v
   Ask Customer   Select
    to Select     Appointment
         |          |
         +-----+----+
               |
               v
      Ask for Confirmation
               |
               v
      Customer Confirms?
          /         \
        Yes          No
         |            |
         v            v
   Delete Calendar   Keep Booking
       Event
         |
         v
   Update PostgreSQL
         |
         v
  Cancellation Complete
```

## Testing

Run the test suite using:

```bash
python -m pytest -v
```

Run an individual test file:

```bash
python -m pytest tests/test_agent_flows.py -v -s
```

Run a specific test:

```bash
python -m pytest tests/test_normalization.py -v
```

## Security Considerations

- Store API keys and credentials in environment variables.
- Keep Google OAuth credentials out of version control.
- Validate and normalize customer phone numbers.
- Validate appointment details before database operations.
- Use customer confirmation before destructive operations such as cancellation.
- Protect customer information and database access.
- Implement appropriate authentication and authorization before exposing business operations publicly.

## Future Enhancements

The following capabilities are potential extensions of the project:

- Appointment rescheduling with Google Calendar synchronization.
- Automated appointment reminders.
- Multilingual voice conversations.
- Human-agent call transfer.
- Customer history and CRM integration.
- Lead qualification and management.
- Business-specific RAG knowledge bases.
- Call analytics and reporting dashboard.
- Multi-tenant SaaS architecture.
- Automated follow-up calls.

## Project Goal

The long-term goal is to build an intelligent AI receptionist platform that helps small businesses automate customer communication, appointment management and repetitive administrative tasks through natural voice interactions.

---

**Built with Python, FastAPI, LangGraph and AI.**