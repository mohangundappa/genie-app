# Deployment & Operations — Trade-offs & Design Decisions

## Deployment Architecture

```
┌─────────────────┐         ┌─────────────────┐
│   Frontend      │         │   Backend       │
│   (Static CDN)  │────────▶│   (Fly.io)      │
│   Vite build    │  REST   │   FastAPI +     │
│   dist/         │  API    │   SQLite        │
└─────────────────┘         └────────┬────────┘
                                     │
                            ┌────────▼────────┐
                            │ Persistent Vol  │
                            │ /data/app.db    │
                            │ (1GB SQLite)    │
                            └─────────────────┘
```

### Why separate frontend and backend deployments

| Approach | Trade-off |
|----------|-----------|
| **Separate (chosen)** | Frontend is static files served from CDN — instant global load times, zero backend load for UI. Backend scales independently. Allows different deployment cadences. |
| **Monolithic (FastAPI serves React)** | Single deployment, simpler infrastructure. But static files go through Python's ASGI server, adding unnecessary latency. Frontend changes require backend redeployment. |
| **Serverless functions** | Auto-scaling, pay-per-use. But cold starts (5-15s) are terrible for an interactive chat UX. SQLite doesn't work in ephemeral serverless environments. |

---

## Backend Deployment: Fly.io

### Why Fly.io

| Alternative | Trade-off |
|-------------|-----------|
| **AWS EC2/ECS** | Full control, any configuration. But requires VPC setup, load balancers, security groups, IAM — massive operational overhead for a single-container app. |
| **Heroku** | Similar simplicity to Fly.io. But no persistent volumes for SQLite, ephemeral filesystem resets on restart. Would force PostgreSQL, adding complexity. |
| **Vercel/Railway** | Easy deployment. Vercel is frontend-focused and doesn't support persistent volumes. Railway supports SQLite but with less control over regions. |
| **Docker + VPS** | Cheapest at scale. But requires managing the server, updates, SSL, monitoring, backups. |
| **Fly.io (chosen)** | Persistent volumes for SQLite, Docker-based deployment, global edge network, simple CLI. Good balance of simplicity and capability. |

### Persistent Volume for SQLite

**Decision**: Deploy with a 1GB persistent volume mounted at `/data`.

- **Why not in-memory**: Query history and API key settings need to survive restarts.
- **Why SQLite on volume, not PostgreSQL**: Eliminates the need for a separate database service. Simplifies deployment to a single container + volume. SQLite handles the read-heavy, low-concurrency workload well.
- **Risk**: Persistent volumes are single-AZ. If the host machine fails, there's a brief period where the volume may be unavailable. Acceptable for a demo; production would need backups.

### Environment Variables

| Variable | Location | Purpose |
|----------|----------|---------|
| `DATABASE_PATH` | Backend `.env` or deployment env | Override SQLite file path (defaults to `./genie.db` locally, `/data/app.db` in production) |
| `OPENAI_API_KEY` | Backend `.env` or DB settings | LLM API key (env var takes precedence, DB allows runtime updates) |
| `OPENAI_MODEL` | Backend `.env` or DB settings | Model name (defaults to `gpt-4o-mini`) |
| `VITE_API_URL` | Frontend `.env` | Backend API base URL (must be updated before frontend build for production) |

---

## Frontend Deployment: Static CDN

### Build process

```bash
npm run build  →  tsc -b && vite build  →  dist/
```

The build produces:
- `dist/index.html` — Entry point (0.46 KB)
- `dist/assets/index-*.css` — All styles (16 KB, gzip: 4 KB)
- `dist/assets/index-*.js` — All JavaScript (608 KB, gzip: 171 KB)

### Bundle size analysis

| Dependency | Approx. Size | Justification |
|------------|-------------|---------------|
| React + ReactDOM | ~140 KB | Core framework |
| Recharts | ~300 KB | Charting library (largest dependency) |
| Lucide icons | ~50 KB | Icon set (tree-shaken) |
| Application code | ~50 KB | Components, hooks, types |
| Tailwind CSS | ~16 KB | Utility classes (purged) |

**Trade-off**: The 608 KB bundle is above the recommended 500 KB threshold. Options to reduce:
1. **Code-split charts**: `React.lazy(() => import('./ChartView'))` — only load charting code when a chart is displayed. Would save ~300 KB on initial load.
2. **Replace Recharts with lighter alternative**: `chart.js` (~60 KB) but with a worse React integration.
3. **Use CDN for React**: Load React from a CDN to leverage browser caching across sites. But introduces an external dependency.

For v1, the bundle size is acceptable. Users wait 1-2s for initial load, then the app is fully interactive.

---

## Security Considerations

### CORS

The backend allows all origins (`allow_origins=["*"]`). This is intentional for development and demo use, but should be restricted to the frontend domain in production:

```python
allow_origins=["https://your-frontend-domain.com"]
```

### Rate Limiting

No rate limiting is implemented. In production, add:
- Request rate limiting per IP (e.g., 60 requests/minute) to prevent abuse.
- OpenAI API call limiting (LLM calls are expensive) — e.g., 20 questions/minute per user.

### Authentication

No authentication is implemented. The app is publicly accessible. For an organization deployment:
- Add OAuth 2.0 / OIDC integration (e.g., Okta, Auth0, Azure AD).
- Per-user query history and settings.
- Role-based access to datasets.

---

## Monitoring & Observability

### Current state
- Backend logs via `uvicorn` (request/response logging)
- Fly.io deployment logs via `fly logs`
- No structured logging, metrics, or tracing

### Production recommendations
1. **Structured logging**: Use `structlog` to emit JSON logs with request IDs, query durations, and LLM token usage.
2. **Metrics**: Track query latency (p50, p95, p99), LLM call success rate, and dataset sizes.
3. **Error tracking**: Integrate Sentry for unhandled exceptions.
4. **Cost monitoring**: Track OpenAI API token usage per user to manage LLM costs.

---

## Scaling Considerations

| Dimension | Current Limit | Scaling Path |
|-----------|---------------|-------------|
| **Concurrent users** | ~50 (single SQLite writer) | PostgreSQL or read replicas |
| **Dataset size** | ~10,000 rows per table | DuckDB for analytical queries, or push to a data warehouse |
| **Query complexity** | Single-table queries | Fine-tuned text-to-SQL model for multi-table JOINs |
| **LLM latency** | 1-3s per question | Streaming responses, query caching |
| **Geography** | Single region | Multi-region Fly.io deployment with replicated volumes |
