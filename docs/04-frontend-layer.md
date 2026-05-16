# Frontend Layer — Trade-offs & Design Decisions

## Framework: React + Vite + TypeScript

### Why this stack

| Alternative | Trade-off |
|-------------|-----------|
| **Next.js** | Adds SSR, routing, and API routes. Overkill for a single-page chat app with no SEO requirements. Vite is faster for development and produces a simpler deployment artifact (static files). |
| **Vue.js** | Comparable capability. React was chosen for broader ecosystem familiarity and richer component libraries (shadcn/ui, recharts). |
| **Svelte** | Lighter runtime, faster rendering. But smaller ecosystem, fewer charting libraries, and less hiring familiarity. |
| **Plain HTML/JS** | No build step, simplest deployment. But no component reuse, no TypeScript safety, painful state management for a chat UI. |

### What TypeScript gives us
- **Type safety on API responses**: `AskResponse`, `ChartConfig`, etc. ensure the frontend correctly handles all response shapes.
- **Refactoring confidence**: Renaming a field in the API response type immediately highlights all consuming components.
- **Editor autocomplete**: Faster development with IntelliSense on all data structures.

### What TypeScript costs
- Build step required (can't just open `index.html`).
- Slightly more verbose code (type annotations, interface definitions).
- Occasional type gymnastics with third-party libraries.

---

## Styling: Tailwind CSS

### Why Tailwind over alternatives

| Alternative | Trade-off |
|-------------|-----------|
| **CSS Modules** | Scoped by default, standard CSS syntax. But requires context-switching between files, slower iteration for rapid prototyping. No utility classes for common patterns (flex, grid, spacing). |
| **styled-components** | Co-located styles with components, dynamic styling via props. But runtime CSS-in-JS adds bundle size and performance overhead. Tailwind is zero-runtime. |
| **Material UI / Ant Design** | Pre-built components with consistent design. But opinionated styling that's hard to customize, larger bundle size, and "looks like every other Material app". |
| **shadcn/ui (chosen alongside Tailwind)** | Copy-paste components built on Tailwind + Radix. Full control over styling, no dependency lock-in. |

### Dark theme decision
We chose a dark theme (gray-950/900/800 palette with indigo accents) because:
1. **Data dashboard convention**: Most data tools (Databricks, Grafana, Superset) default to dark themes.
2. **Reduced eye strain**: Users analyzing data spend extended periods looking at the screen.
3. **Chart contrast**: Charts and data visualizations pop better against dark backgrounds.

**Trade-off**: No light mode toggle. Adding one would require a theme context provider and conditional classes throughout. Not worth the complexity for v1.

---

## Component Architecture

### Chat-based UI vs. Dashboard UI

This is the most significant UX decision in the entire project.

| Approach | Pros | Cons |
|----------|------|------|
| **Chat-based (chosen)** | Natural, conversational. Users don't need to know SQL or navigate complex forms. Matches Databricks Genie's UX. Easy to show progressive results. | Harder to compare multiple queries side-by-side. Conversation history grows long. Each message is a "snapshot" — can't easily modify a previous query. |
| **Dashboard with query builder** | Better for power users. Side-by-side comparisons. Persistent filter states. | Higher learning curve. More complex UI. Doesn't feel as "AI-native". |
| **Notebook-style (like Jupyter)** | Cells can be re-executed. Mix of text and code. | Intimidating for non-technical users. Complex state management. |

We chose the chat-based approach because it aligns with the Databricks Genie mental model and is the most accessible for non-technical users.

### Component breakdown

#### `App.tsx` — Application Shell
- **Responsibility**: Layout (sidebar + main content), routing state, message management.
- **Trade-off**: All state lives here (messages, input, loading, sidebar, settings). This is fine for the current scale but would need extraction to a context/store if we added features like multi-conversation, collaborative editing, or persistent sessions.

#### `ChartView.tsx` — Visualization Engine
- **Responsibility**: Renders bar, line, pie, area, and scatter charts from data + config.
- **Library**: Recharts (React-native charting library).

| Alternative | Trade-off |
|-------------|-----------|
| **D3.js** | Maximum flexibility and customization. But imperative API clashes with React's declarative model. Requires significant boilerplate for basic charts. |
| **Chart.js** | Canvas-based (fast for large datasets). But React wrapper (react-chartjs-2) is less maintained. Customization requires understanding Chart.js internals. |
| **Plotly** | Best for scientific/statistical charts. But large bundle size (~3MB), opinionated styling, and React integration is a thin wrapper around the imperative API. |
| **Recharts (chosen)** | Declarative, React-native, reasonable defaults. Good balance of simplicity and customization. Smaller bundle than Plotly. |
| **Nivo** | Beautiful defaults, built on D3. But less flexibility for custom chart types and slightly more complex API. |

**Trade-off accepted**: Recharts doesn't support some advanced chart types (heatmaps, treemaps, sankey diagrams). If advanced visualizations are needed, Plotly would be the better choice despite its larger bundle.

#### `ResultsTable.tsx` — Data Grid
- **Responsibility**: Renders query results as a scrollable table.
- **Design decisions**:
  - Max height with scroll (not pagination). Users can see all data without clicking through pages.
  - Number formatting (locale-aware thousands separators, 2 decimal places for floats).
  - Null values displayed as "—" (em dash) for clarity.

| Alternative | Trade-off |
|-------------|-----------|
| **AG Grid** | Full-featured data grid with sorting, filtering, column resizing, virtualization. But adds ~200KB to bundle and has a complex API. Overkill for displaying query results. |
| **TanStack Table** | Headless table with hooks for sorting/filtering. More flexible but requires building all UI from scratch. Would be worth it if we needed column sorting or filtering. |
| **Simple HTML table (chosen)** | Minimal bundle impact, full styling control. Sufficient for displaying up to 100 rows. |

**Trade-off accepted**: No client-side sorting or column resizing. These would be valuable features but add complexity. Users can re-query with `ORDER BY` for sorting.

#### `SqlDisplay.tsx` — SQL Viewer
- **Responsibility**: Shows the generated SQL query with syntax highlighting and copy button.
- **Design decision**: Basic keyword uppercasing instead of a full syntax highlighter.

| Alternative | Trade-off |
|-------------|-----------|
| **Prism.js / Highlight.js** | Proper token-level syntax highlighting with themes. But adds ~50KB for a single use case. |
| **Monaco Editor** | Full VS Code editor experience with autocomplete. Massive overkill (~5MB). |
| **Regex uppercasing (chosen)** | Lightweight (~20 lines of code), readable output. Not perfect highlighting but sufficient for displaying generated SQL. |

#### `DatasetExplorer.tsx` — Schema Browser
- **Responsibility**: Sidebar tree view of datasets with expandable column lists.
- **Design decisions**:
  - Shows row count badge per table (helps users estimate query result size).
  - Shows column types (helps users understand what questions to ask).
  - "Ask about this dataset" action button pre-fills the query input.

#### `SettingsModal.tsx` — Configuration
- **Responsibility**: API key and model configuration.
- **Security decision**: API key input uses `type="password"`. The GET endpoint only returns a masked preview (`sk-...xxxx`), never the full key.

#### `QueryHistory.tsx` — Recent Queries
- **Responsibility**: Shows past questions for quick re-execution.
- **Trade-off**: History is loaded from the backend (persisted in SQLite) rather than browser localStorage. This means history survives browser changes but is shared across all users (no auth system). In a multi-user production system, history would be per-user.

---

## State Management

### Why no Redux / Zustand / Jotai?

The application state is simple:
- `messages[]` — conversation history
- `input` — current text input
- `loading` — request in progress
- `sidebarOpen`, `sidebarTab`, `settingsOpen` — UI state
- `activeView` — table vs. chart toggle

All state is local to `App.tsx` and flows down via props. No component needs to update state in a sibling without going through the parent.

**When to reconsider**: Add a state management library if we introduce:
- Multi-conversation support (switching between conversations)
- Real-time collaboration (multiple users seeing the same state)
- Complex undo/redo (reverting queries)
- Global notification system

---

## API Client (`useApi.ts`)

### Design decisions

1. **Custom hook, not a library**: We use a simple `fetch` wrapper instead of React Query, SWR, or Axios.
   - **Why**: The app has minimal caching needs (most queries are unique). React Query's cache invalidation, retry logic, and refetching would add complexity without clear benefit.
   - **When to switch**: If we added dashboards with auto-refreshing data or offline support, React Query would be valuable.

2. **Centralized error handling**: All API errors are caught and surfaced as chat messages. The user never sees a blank screen or unhandled exception.

3. **Configurable base URL**: Reads from `VITE_API_URL` environment variable. This allows the same frontend code to point to localhost (development) or the deployed backend (production) without code changes.

---

## Performance Considerations

| Aspect | Current approach | Trade-off |
|--------|-----------------|-----------|
| **Bundle size** | ~608KB (gzip: ~171KB) | Recharts is the largest dependency (~300KB). Acceptable for a data tool. Could code-split charts with `React.lazy()`. |
| **Re-renders** | `useCallback` on `handleSubmit` to prevent unnecessary re-renders of child components | Minimal optimization needed given the small component tree |
| **Table rendering** | Caps at 100 rows client-side | For 10,000+ row results, would need virtualization (react-window) or server-side pagination |
| **Chart rendering** | SVG-based (Recharts default) | SVG slows down with 1000+ data points. For large datasets, Canvas-based charts (Chart.js) would be faster |
