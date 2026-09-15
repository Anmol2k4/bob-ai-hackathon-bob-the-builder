# Source Code

The current runnable prototype is a dependency-free Python service and static dashboard.

## Structure

```text
src/
  app.py              HTTP API and deterministic seeded intelligence
  .env.example        Optional IBM Bob integration variables
  static/
    index.html        Dashboard structure
    styles.css        Product styling and responsive layout
    app.js            API-backed dashboard interactions
```

## Start

From the repository root, run `python src/app.py` and open `http://127.0.0.1:8000`.

## Future integrations

The API is organized around JSON contracts so the seeded structures can be replaced with SQLite, live protocol extraction, and authenticated IBM Bob/MCP calls in the next implementation pass.

## What NOT to Include in src/

- `.env` files with real secrets
- `node_modules/` or virtual environments
- Build artifacts or generated caches
