// Backend API origin. Empty = same-origin, which is the setup: one Render
// service serves these pages, the API and /docs together.
//
// The value exists at all because there used to be a second, static-site
// service that had no API of its own and needed the backend's URL baked in at
// build time. That service is gone (see render.yaml for why), but the hook
// stays: putting a static front end or a CDN back is a one-line change here,
// not a code change.
window.MYNA_API_BASE = "";
