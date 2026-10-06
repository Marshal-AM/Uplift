#!/bin/sh
# Deploy masumi-payment-service (pinned) to the Railway service `mps`.
# Its image does not migrate or seed, so the start command is patched to: migrate → seed once → start.
# Variables (DATABASE_URL, ENCRYPTION_KEY, ADMIN_KEY, BLOCKFROST_API_KEY_PREPROD, …) live on the Railway service.
set -e
COMMIT=d569a338ca54d5be7441564770d75ebf89b71f12
PROJECT=7e46ce06-91f2-457e-b6f0-b25e3f80cb1e
DIR="${TMPDIR:-/tmp}/uplift-mps"
rm -rf "$DIR" && git clone -q https://github.com/masumi-network/masumi-payment-service.git "$DIR"
cd "$DIR" && git checkout -q "$COMMIT"
mkdir -p frontend/dist   # target of src/frontend/dist symlink; the image builds the real one
sed -i.bak 's#^CMD \[ "pnpm", "run", "start" \]#CMD ["sh", "-c", "pnpm run prisma:migrate \&\& (pnpm run prisma:seed > /dev/null 2>\&1 || echo seed-failed) \&\& pnpm run start"]#' Dockerfile
# the seed script imports the workspace package @masumi/payment-core, which the runner stage does not copy
sed -i.bak 's#^COPY --from=backend-builder /usr/src/app/prisma ./prisma#&\
COPY --from=backend-builder /usr/src/app/packages ./packages#' Dockerfile
grep -q 'prisma:migrate' Dockerfile && grep -q 'app/packages ./packages' Dockerfile || { echo "Dockerfile patch did not apply"; exit 1; }
railway up --project "$PROJECT" --environment production --service mps --detach
