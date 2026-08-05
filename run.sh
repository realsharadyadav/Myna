#!/usr/bin/env bash
# Local dev: two processes, same split as production.
#
#   :8000  the API (uvicorn)          — JSON only, serves no pages
#   :5173  the UI  (app/static)       — plain HTML, talks to :8000 over REST
#
# Two commands rather than one is the point. The backend stopped serving the
# front end so that there is exactly one way the UI reaches it — the same way a
# mobile app will. Running them together locally would quietly undo that.
set -e
cd "$(dirname "$0")"

if [ ! -d ".venv" ]; then
  python3 -m venv .venv
  ./.venv/bin/pip install -q -r requirements.txt
fi

case "${1:-all}" in
  api)
    exec ./.venv/bin/uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
    ;;
  ui)
    exec ./.venv/bin/python -m http.server 5173 --directory app/static
    ;;
  all)
    ./.venv/bin/uvicorn app.main:app --reload --host 0.0.0.0 --port 8000 &
    api_pid=$!
    trap 'kill $api_pid 2>/dev/null' EXIT
    echo "API  http://localhost:8000/docs"
    echo "App  http://localhost:5173/"
    echo "Panel http://localhost:5173/admin.html"
    exec ./.venv/bin/python -m http.server 5173 --directory app/static
    ;;
  *)
    echo "usage: ./run.sh [all|api|ui]" >&2
    exit 2
    ;;
esac
