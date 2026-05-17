---
name: testing-genie-app
description: Test the Data Genie app end-to-end. Use when verifying backend API, frontend UI, or new feature changes.
---

# Testing Data Genie App

## Prerequisites

- Python 3.11+ with Poetry installed
- Node.js 18+ with npm
- No external services required (SQLite is embedded)

## Devin Secrets Needed

- `OPENAI_API_KEY` (optional) — needed for full LLM-powered SQL generation. Without it, the app falls back to a pattern matcher. Configure via Settings page in the UI or set in environment.

## Starting the App

### Backend (port 8000)
```bash
cd genie-backend
poetry install
poetry run fastapi dev app/main.py --port 8000 --host 0.0.0.0
```

### Frontend (port 5173)
```bash
cd genie-frontend
npm install
npm run dev -- --host 0.0.0.0
```

The frontend is at `http://localhost:5173` and the backend API at `http://localhost:8000`.

## Database

SQLite database at `genie.db` in the project root. Tables are auto-created on first backend startup. To reset, delete `genie.db` and restart the backend — all seed data (semantic layer, benchmark cases, instructions) will be re-created.

**Important**: The running server holds the DB connection. Deleting `genie.db` while the server is running may not take effect until restart.

## Key API Endpoints for Testing

| Endpoint | Method | Purpose |
|----------|--------|---------|
| `/api/ask` | POST | Main NL-to-SQL endpoint (body: `{"question": "..."}`) |
| `/api/feedback/submit` | POST | Submit thumbs up/down vote |
| `/api/feedback/stats` | GET | Get feedback statistics |
| `/api/benchmark/cases` | GET | List benchmark test cases |
| `/api/benchmark/run` | POST | Run all benchmark cases |
| `/api/semantic/instructions` | GET | List all instructions |
| `/api/semantic/instructions` | POST | Add instruction |
| `/api/semantic/instructions/{id}` | DELETE | Delete instruction |

## Testing Checklist

1. **Ask a question** — verify response includes `query_id`, SQL, results, and feedback buttons
2. **Thumbs up** — click and verify "Thanks!" appears, check `/api/feedback/stats` for correct count
3. **Thumbs down** — click, type comment, press Enter. Verify only 1 feedback record created (not 2)
4. **Quality panel** — click "Quality" tab, verify 3 sub-tabs: Feedback, Benchmark, Instructions
5. **Instructions CRUD** — add a new instruction, verify it appears in the list, delete it
6. **Benchmark tab** — verify "Run Benchmark (N cases)" button shows correct count
7. **Trusted queries** — ask a question like "Average salary by department" and verify "Trusted Query" badge

## Common Pitfalls

- **query_id scope**: The `query_id` field lives on the `PipelineContext` dataclass. If you see NameError referencing `query_id`, check that it's accessed as `ctx.query_id` (not as a bare variable).
- **Feedback double-submit**: Downvote flow defers the API call until comment step completes (Enter or blur). If you see duplicate feedback records, check the frontend `FeedbackButtons` component.
- **SQL injection in parameterized queries**: Parameter values extracted from user questions are sanitized by escaping single quotes before SQL substitution. If adding new parameterized query features, ensure sanitization is applied.
- **No OpenAI key**: Without an API key, the SQL generator uses a pattern matcher fallback that may not use the schema retriever's table selection correctly. This is expected behavior — the retriever itself still works.
- **Delete button UX**: The trash icon on instruction cards is small. When testing deletion via UI, you may need to be very precise with clicks. Consider verifying via API as a fallback.
