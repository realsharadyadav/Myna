// Backend API origin, and the only thing these pages need to know about it.
//
// Empty = same-origin, which is right for local dev and for hitting the
// backend service directly. The static front-end deploy overwrites this file
// at build time with the backend's URL (see render.yaml).
//
// This one value is the whole coupling between the two deploys. If it points
// somewhere wrong, every request fails while both services still report
// healthy — so the app probes /api/food/health when a request fails and names
// this address, rather than telling the user to check their connection.
window.MYNA_API_BASE = "";
