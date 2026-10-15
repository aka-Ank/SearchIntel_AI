#!/usr/bin/env bash
set -euo pipefail

root_dir="$(cd "$(dirname "$0")/../.." && pwd)"
run_id="$$"
redis_port="16379"
redis_name="searchintel-e2e-redis-${run_id}"
db_path="/tmp/searchintel-e2e-${run_id}.db"
log_dir="/tmp/searchintel-e2e-logs-${run_id}"
mkdir -m 700 "$log_dir"
api_pid=""
worker_pid=""
fixture_pid=""
competitor_fixture_pid=""
frontend_pid=""

cleanup() {
	for process_id in "$frontend_pid" "$worker_pid" "$api_pid" "$fixture_pid" "$competitor_fixture_pid"; do
		if [[ -n "$process_id" ]]; then
			pkill -TERM -P "$process_id" >/dev/null 2>&1 || true
			kill "$process_id" >/dev/null 2>&1 || true
		fi
	done
	docker rm -f "$redis_name" >/dev/null 2>&1 || true
	rm -f "$db_path" "$db_path-shm" "$db_path-wal"
	if [[ "${1:-0}" != "0" ]]; then
		for log in "$log_dir"/*; do
			if [[ -f "$log" ]]; then tail -40 "$log"; fi
		done
	fi
	rm -rf "$log_dir"
}
on_exit() { status=$?; cleanup "$status"; exit "$status"; }
trap on_exit EXIT INT TERM

if docker ps -a --format '{{.Names}}' | rg -q "^${redis_name}$"; then
	echo "Refusing to use pre-existing test container: ${redis_name}" >&2
	exit 2
fi
docker run --rm --detach --name "$redis_name" -p "127.0.0.1:${redis_port}:6379" redis:7-alpine >/dev/null
for _ in $(seq 1 30); do
	if docker exec "$redis_name" redis-cli ping 2>/dev/null | rg -q PONG; then break; fi
	sleep 1
done

export DATABASE_URL="sqlite:////tmp/searchintel-e2e-${run_id}.db"
export REDIS_URL="redis://127.0.0.1:${redis_port}/0"
export AUTH_SECRET="playwright-test-secret-0123456789-0123456789-0123456789"
export APP_ENV=local
export AUTH_COOKIE_SAMESITE=strict
export ALLOW_LOCAL_URLS=true
export CRAWLER_REQUEST_DELAY_SECONDS=0
export VECTOR_STORE_PROVIDER=memory
export SEARCHINTEL_API_ORIGIN=http://127.0.0.1:18000

cd "$root_dir"
uv run --directory "$root_dir/backend" alembic upgrade head >"$log_dir/migration.log" 2>&1
python3 -m http.server 18888 --bind 127.0.0.1 --directory "$root_dir/frontend/e2e/fixtures/site" >"$log_dir/fixture.log" 2>&1 &
fixture_pid=$!
python3 -m http.server 18889 --bind 127.0.0.1 --directory "$root_dir/frontend/e2e/fixtures/competitor" >"$log_dir/competitor-fixture.log" 2>&1 &
competitor_fixture_pid=$!
uv run --directory "$root_dir/backend" celery -A app.tasks.queue:celery_app worker --pool=solo --concurrency=1 --queues=crawls,audits --loglevel=WARNING >"$log_dir/worker.log" 2>&1 &
worker_pid=$!
uv run --directory "$root_dir/backend" uvicorn app.main:app --host 127.0.0.1 --port 18000 >"$log_dir/api.log" 2>&1 &
api_pid=$!
cd "$root_dir/frontend"
npm run dev -- --hostname 127.0.0.1 --port 13000 >"$log_dir/frontend.log" 2>&1 &
frontend_pid=$!

ready=0
for _ in $(seq 1 90); do
	if curl -fsS http://127.0.0.1:18000/api/v1/health/ready >/dev/null 2>&1 && \
		curl -fsS http://127.0.0.1:13000 >/dev/null 2>&1 && \
		curl -fsS http://127.0.0.1:18888 >/dev/null 2>&1 && \
		curl -fsS http://127.0.0.1:18889 >/dev/null 2>&1; then
		ready=1
		break
	fi
	sleep 1
done
if [[ "$ready" != "1" ]]; then
	echo "Local E2E services did not become ready; see test runner logs." >&2
	exit 3
fi
npx playwright test
