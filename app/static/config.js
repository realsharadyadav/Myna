// Backend API origin. Empty = same-origin, which is the current setup: one
// Render service serves these pages, the API and /docs together.
//
// This hook is kept because a static front end or CDN in front is a one-line
// change *here*. The line is one line; the consequences are not. Splitting the
// front end off again brings back, by construction:
//
//   - /docs and /api/* returning 404 on the static host, which has neither
//   - the front end serving whatever HTML was last built, going stale silently
//     while the backend is already current
//   - this very value pointing at the wrong or a dead backend, which breaks
//     every request while both services still report healthy
//
// Two things that used to fail no longer can: the pages read this value rather
// than assuming same-origin (they hardcoded an empty base before), and the app
// is named index.html so a static host has a root document at all.
//
// The third failure — a wrong value here — is now at least visible: the app
// probes /api/food/health when a request fails and names this address instead
// of blaming the user's connection. If you do split it again, deploy both
// services from the same commit, every time.
window.MYNA_API_BASE = "";
