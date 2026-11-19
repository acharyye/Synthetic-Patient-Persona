from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # Which LLM backend the adapter uses when live: null | ollama | anthropic.
    # Defaults to the local one — cloud is opt-in, per the offline-first promise.
    llm_backend: str = "ollama"

    ollama_host: str = "http://localhost:11434"
    ollama_model: str = "qwen2.5:7b-instruct"
    # Seconds to wait for one generation. A schema-constrained call against a
    # freshly loaded 7B exceeded the old hard-coded 120 and the adapter fell back
    # to the null backend mid-record — caught by the recorder's guard, but only
    # because that guard exists. Generous by default: a slow answer is a slow
    # answer, while a timeout is indistinguishable from a model that would not
    # respond.
    ollama_timeout: int = 600

    anthropic_api_key: str = ""
    anthropic_model: str = "claude-sonnet-5"

    # Master seed for reproducible cohorts and simulations. Every artifact should
    # record this alongside the derived seed paths (see foundation/rng.py).
    master_seed: int = 42

    # Matches docker-compose, which offsets the host port to avoid colliding
    # with another Neo4j on the standard 7687.
    neo4j_uri: str = "bolt://localhost:7688"
    neo4j_user: str = "neo4j"
    neo4j_password: str = "please-change-me"

    # When False, external calls (LLM, graph) are replaced by deterministic stubs
    # so the whole pipeline runs offline. Flip to True once creds are in place.
    spp_live: bool = False

    @field_validator("spp_live", mode="before")
    @classmethod
    def _tolerate_an_empty_flag(cls, value):
        """`SPP_LIVE=` is absent, not false-with-a-typo.

        Shell users write `unset FOO` and `FOO=` interchangeably, and pydantic
        rejects an empty string for a bool outright. That produced 33 collection
        errors across the whole suite — a red run that means nothing about the
        code — from one character in one environment variable. Treating empty as
        unset is the only reading that matches what the person meant.

        Anything else still fails loudly. `SPP_LIVE=yes` is a typo worth a
        traceback; silently accepting it would make a live run look offline,
        which is the failure direction that actually costs something.
        """
        if isinstance(value, str) and not value.strip():
            return False
        return value


settings = Settings()
