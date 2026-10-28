# Frontend — AI Music Marketer Web

Next.js 15 (App Router) UI for the AI Music Marketer app.

## Stack

- Next.js 15 / React 19
- TypeScript
- Tailwind CSS 4 (`@tailwindcss/postcss`)
- `recharts` for dashboard charts, `lucide-react` for icons

## Structure

```text
app/
  page.tsx                    # dashboard
  campaigns/page.tsx          # campaign list
  campaigns/new/page.tsx      # create campaign
  campaigns/[id]/page.tsx     # campaign detail
  layout.tsx, globals.css
lib/
  api.ts                      # API client (bearer token)
  contracts.ts                # shared request/response types
```

## Scripts

```bash
npm install
npm run dev        # dev server on 0.0.0.0
npm run build      # production build
npm start          # production server
npm run typecheck  # tsc --noEmit
npm run lint       # eslint
```

The API base URL and bearer token are configured via environment variables used by `lib/api.ts`; see `.env.example` at the repository root.
