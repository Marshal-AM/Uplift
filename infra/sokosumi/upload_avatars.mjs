// Upload each coworker's avatar (infra/sokosumi/avatars → landing/public/avatars, 512 px) to Sokosumi preprod.
// Core takes the image as a multipart file on POST /v1/coworkers/{id}/image (owner only), so this reuses the
// signed-in Sokosumi CLI session: run it through the CLI's own package (see infra/sokosumi/README or below).
//
//   SOKOSUMI_CLI_ROOT=<path to node_modules/@masumi_network/sokosumi> npx -y -p node@24 node infra/sokosumi/upload_avatars.mjs
//
// The bearer token stays in this process; nothing is printed but the per-coworker result.
import { readFileSync } from "node:fs";
import { createRequire } from "node:module";
import { dirname, join } from "node:path";

const cliRoot = process.env.SOKOSUMI_CLI_ROOT
  ?? dirname(createRequire(join(process.cwd(), "noop.js")).resolve("@masumi_network/sokosumi/package.json"));
const { bootstrapCliSession, requireAuthenticatedSession } = await import(join(cliRoot, "dist/src/auth/bootstrap.js"));

const ids = JSON.parse(readFileSync("infra/.secrets/coworkers.json", "utf8"));
const session = bootstrapCliSession({ preprod: true });
await requireAuthenticatedSession(session);
const token = await session.authManager.getAuthTokenAsync({
  authBaseUrl: session.config.authBaseUrl, clientId: session.config.clientId,
  clientSecret: session.config.clientSecret, environment: session.env,
});

for (const [role, { id }] of Object.entries(ids)) {
  const form = new FormData();
  form.append("file", new Blob([readFileSync(`landing/public/avatars/${role}.png`)], { type: "image/png" }), `${role}.png`);
  const res = await fetch(`${session.config.apiUrl}/v1/coworkers/${id}/image`, {
    method: "POST", headers: { Authorization: `Bearer ${token}` }, body: form,
  });
  const body = await res.json().catch(() => ({}));
  console.log(role.padEnd(7), res.status, res.ok ? (body.data?.image ?? body.image ?? "ok") : JSON.stringify(body).slice(0, 200));
}
