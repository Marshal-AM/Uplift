#!/bin/sh
# Ray head → Kodosumi panel/spooler → (re)boot the `uplift` Expose. Data lives in /data (a mounted volume).
set -e
PORT="${PORT:-3370}"
mkdir -p /data && cd /data
export KODO_APP_SERVER="http://0.0.0.0:${PORT}" KODO_URL="http://127.0.0.1:${PORT}"
ray start --head --port=6379 --dashboard-host=127.0.0.1 --disable-usage-stats --num-cpus="${RAY_CPUS:-2}" --object-store-memory=500000000
koco start --level info &
PANEL=$!
until python -c "import httpx,os; httpx.get(os.environ['KODO_URL'] + '/health', timeout=2)" 2>/dev/null; do sleep 2; done
python /app/infra/kodosumi/boot.py || echo "boot failed; panel stays up for inspection"
wait $PANEL
