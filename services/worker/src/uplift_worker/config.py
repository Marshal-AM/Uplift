import json
from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict

ROLES = ["nora", "kai", "rafael", "priya", "marcus", "clara", "iris", "oskar", "yuki", "leo", "sasha", "ruth", "quinn"]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str
    public_url: str  # this Worker's https URL (chat baseURL, hooks)
    sokosumi_api_url: str = "https://api.preprod.sokosumi.com"
    # {"nora": {"id": "<coworker uuid>", "key": "coworker_..."}, "kai": {...}, ...}
    coworkers_json: str
    # {"kai": "<sokosumi agent id>", ...} — the Masumi Agents Nora hires as Jobs
    agent_ids_json: str = "{}"
    # {"nora": "<masumi agentIdentifier>", "kai": "...", ...} for paid-Task terms
    agent_identifiers_json: str = "{}"
    prices_json: str = ('{"nora": 1.5, "kai": 1.25, "rafael": 1.25, "priya": 1.5, "marcus": 1.25, "clara": 2.0, '
                        '"iris": 2.5, "oskar": 1.5, "yuki": 1.0, "leo": 2.0, "sasha": 1.5, "ruth": 0.25, "quinn": 0.5}')

    gateway_url: str
    gateway_read_key: str
    connect_state_secret: str
    read_capability_secret: str
    worker_hook_secret: str

    kodo_url: str
    kodo_admin_user: str = "admin"
    kodo_admin_password: str

    payments_enabled: bool = False
    mps_url: str = ""  # https://<mps>/api/v1
    mps_token: str = ""  # scoped ReadAndPay key
    network: str = "Preprod"
    tusdm_unit: str = "16a55b2a349361ff88c03788f93e1e966e5d689605d044fef722ddde0014df10745553444d"

    cre_trigger_url: str = ""  # deployed: CRE gateway; empty: `cre workflow simulate`
    cre_workflow_id: str = ""
    cre_trigger_private_key: str = ""  # EVM key listed in the workflow's authorizedKeys
    cre_project_dir: str = "../../cre"

    trace_key: str = ""  # agents post their trace events with this key
    trace_view_key: str = ""  # the /live page and e2e/trace.py read with this key
    shopify_api_version: str = "2026-10"  # display only: the Admin API version the gateway calls (rank card)
    trace_origins: str = "https://uplift-landing.up.railway.app,http://localhost:3000"

    artifact_bucket: str = "uplift-artifacts-517207998460"
    aws_region: str = "us-east-1"
    port: int = 8080

    @property
    def coworkers(self) -> dict[str, dict[str, str]]:
        return json.loads(self.coworkers_json)

    @property
    def agent_ids(self) -> dict[str, str]:
        return json.loads(self.agent_ids_json)

    @property
    def agent_identifiers(self) -> dict[str, str]:
        return json.loads(self.agent_identifiers_json)

    @property
    def prices(self) -> dict[str, float]:
        return json.loads(self.prices_json)


@lru_cache
def settings() -> Settings:
    return Settings()
