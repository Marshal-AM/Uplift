"""Create/update the `uplift` Expose on a Kodosumi panel and boot it into Ray Serve.

    KODO_URL=http://localhost:3370 uv run python infra/kodosumi/boot.py

Agent service keys are read from the environment (e.g. a local .env) and injected into the
Ray runtime_env, so they never live in the repository.
"""

import os
import sys

import httpx

PANEL = os.environ.get("KODO_URL", "http://localhost:3370")
USER = os.environ.get("KODO_ADMIN_USER", "admin")
PASSWORD = os.environ.get("KODO_ADMIN_PASSWORD", "admin")
NETWORK = os.environ.get("KODO_NETWORK", "")  # "Preprod" once KODO_MASUMI0 points at the Uplift MPS
FORWARDED_ENV = [
    "AWS_REGION", "BEDROCK_LLM_API_KEY", "ARTIFACT_BUCKET", "GATEWAY_URL", "DATAFORSEO_LOGIN", "DATAFORSEO_PASSWORD",
    "FIRECRAWL_API_KEY", "BRIGHTDATA_API_KEY", "TAVILY_API_KEY", "GEMINI_API_KEY", "GOOGLE_API_KEY", "AWS_ACCESS_KEY_ID",
    "AWS_SECRET_ACCESS_KEY",
]


def bootstrap() -> str:
    env = "\n".join(f'    {k}: "{os.environ[k]}"' for k in FORWARDED_ENV if os.environ.get(k))
    return f"""import_path: uplift_agents.app:fast_app
runtime_env:
  env_vars:
    OTEL_SDK_DISABLED: "true"
{env}
deployments:
  - name: Uplift
    num_replicas: 1
    ray_actor_options:
      num_cpus: 0.5
"""


def main() -> None:
    with httpx.Client(base_url=PANEL, timeout=60) as http:
        http.post("/api/login", json={"name": USER, "password": PASSWORD}).raise_for_status()
        current = http.get("/expose/uplift")
        etag = current.json().get("etag") if current.status_code == 200 else None  # required to change network
        resp = http.post("/expose", json={"name": "uplift", "display": "Uplift", "network": NETWORK,
                                          "enabled": True, "bootstrap": bootstrap(), "etag": etag})
        resp.raise_for_status()
        print("expose:", resp.json().get("state"))
        with http.stream("POST", "/boot", timeout=1800) as stream:
            for line in stream.iter_lines():
                if line.startswith("data: "):
                    print(line[6:])
        items, offset = [], None
        while True:
            page = http.get("/sumi", params={"offset": offset} if offset else None).json()
            items += page.get("items", [])
            offset = page.get("offset")
            if not offset or not page.get("items"):
                break
        for item in items:
            print(f"{item['id']:<16} {item['state']:<8} {item['api_url']}")
        if len(items) < 12 or any(i["state"] != "alive" for i in items):
            sys.exit(f"expected 12 alive Sumi services, found {sum(i['state'] == 'alive' for i in items)}")


if __name__ == "__main__":
    main()
