---
schema: clarification-answers/v1
status: submitted
generated_at: "2026-10-14T17:56:38.968Z"
scope: [frontend, backend, generic]
questions_file: clarification-questions.json
---

# Rearchitecture Clarification Answers

## 🖥️ Frontend

- **F1** Confirm the target frontend framework and version. The implementation prompts specify Next.js, React, TypeScript, and Tailwind CSS, but do not pin framework versions.
  - answer: Next.js + React + TypeScript + Tailwind CSS (latest stable compatible versions)
  - source: user
- **F2** Which component or UI library should the rewritten frontend use? The supplied documents specify Tailwind CSS but do not name a component library.
  - answer: Any is fine
  - source: user
- **F3** Provide paths or URLs to screenshots or recordings of the current UI, or state that no visual reference is available. This helps preserve or intentionally revise existing user-facing flows.
  - answer: Create one from scratch, make sure its decent as this is just a prototype, but make it user friendly and NOT BLAND
  - source: user
- **F4** What design system or token source should guide the rewritten UI? You may provide a design-system link/file or specify a direction such as extracting and matching the existing CSS tokens.
  - answer: Any is fine
  - source: user
- **F5** Which accessibility standard should the frontend target?
  - answer: WCAG 2.1 AA
  - source: user
- **F6** Which browser/runtime targets should the app support?
  - answer: modern evergreen (Chrome, Firefox, Safari, Edge — latest 2 major versions)
  - source: user
- **F7** What responsive layout strategy should the rewritten UI use?
  - answer: Desktop-only
  - source: user
- **F8** Which interface locales are in scope? Enter locale codes, or state that only English is needed for this release.
  - answer: English only
  - source: user
- **F9** Do you have a preference for client/server state management?
  - answer: Framework-native state and server data fetching
  - source: user
- **F10** Do you have a routing preference for the frontend?
  - answer: Next.js App Router
  - source: user

## ⚙️ Backend

- **B1** Confirm the target backend framework and version. The supplied documents specify Python and FastAPI but do not pin a FastAPI version.
  - answer: FastAPI (latest stable compatible version)
  - source: user
- **B2** How should existing API clients be treated while implementing the new /api/v1 contract?
  - answer: must preserve
  - source: user
- **B3** How should existing SQLite song and campaign data be handled when moving toward the PostgreSQL/Alembic structure in the implementation prompts?
  - answer: TBD / assess in research phase
  - source: user
- **B4** What authentication and authorization approach should be used? The API specification requires authorization for private resources and says to inspect any existing identity mechanism before choosing one.
  - answer: preserve existing auth mechanism; detect from codebase
  - source: user
- **B5** What latency, throughput, and availability targets should the first release meet? You may state that this is a local-development milestone with no production SLA yet.
  - answer: This is intended for a presentation, but the zip file needs to be shared and accessed on other devices
  - source: user

## 📋 General

- **G1** What outcome defines success for this rewrite? Specify the required features and how they should be verified.
  - answer: Implement the supplied v2 product, modular implementation, and API specifications; create the complete updated structure and deliver/test the first song-upload → audio-analysis → Song Intelligence → A&R report vertical slice, while preserving required safeguards.
  - source: user
- **G2** Confirm any work that must remain out of scope. The supplied documents state that later roadmap work, production deployment, real external account connections, publishing, distribution, advertising spend, and model training are not authorized by this request.
  - answer: Do not implement later roadmap features beyond the first vertical slice. Do not deploy, connect real external accounts, publish or distribute content, spend money, or train on uploaded music without necessary rights and consent.
  - source: user
- **G3** How should existing tests be treated during the rewrite?
  - answer: can rewrite
  - source: user
- **G4** Where should the rewritten application files go?
  - answer: in-place
  - source: user
- **G5** Add any requirements, exclusions, dependencies, compliance rules, or operational constraints not covered above.
  - answer: None beyond the decisions listed in this specification.
  - source: user
