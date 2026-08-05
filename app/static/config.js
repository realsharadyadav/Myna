// Backend API origin, and the only thing these pages need to know about it.
//
// This one value is the whole coupling between the two deploys. If it points
// somewhere wrong, every request fails while both services still report
// healthy — so the app probes /api/food/health when a request fails and names
// this address, rather than telling the user to check their connection.
//
// In production the static site's build overwrites this file with the backend's
// real URL, which Render resolves from the backend service (see render.yaml).
// Nothing here is hardcoded to a deployed host on purpose.
//
// What's left below is the local-dev case. The backend no longer serves these
// pages, so "same origin" is never the answer during development: ./run.sh
// puts the pages on :5173 and uvicorn on :8000.
window.MYNA_API_BASE =
  location.hostname === "localhost" || location.hostname === "127.0.0.1"
    ? location.protocol + "//" + location.hostname + ":8000"
    : "";
