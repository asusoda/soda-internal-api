"""Turns text into vectors through an OpenAI-compatible embeddings endpoint. No Flask here.

An org sets its own service on the Integrations page. Else the deployment default comes from
EMBEDDINGS_URL (base URL, for example http://llama-embed:8080/v1), EMBEDDINGS_MODEL and
EMBEDDINGS_API_KEY. Without either there is no embedder: writers send their own vectors and search
runs on text alone. If the base URL is OpenRouter's and no embeddings key is set, the embedder uses
the org's OpenRouter key, else OPENROUTER_API_KEY. The query prefix is put before search queries, for
models that embed queries and documents differently (Qwen3-Embedding takes an instruction). Search
compares only vectors of the same model, so orgs with different models do not mix.

An org's embedder counts each text it embeds against the org's knowledge.embeddings_per_day limit, also for
agent memory, whichever service it uses.
"""

import os
from collections.abc import Callable
from dataclasses import dataclass, field, replace

import requests

from core import limits, net, secrets
from core.integrations import openrouter
from core.integrations.registry import Field, Integration, IntegrationError, org_values, register, use
from core.log import get_logger
from modules.knowledge.models import DIMENSIONS

logger = get_logger("knowledge.embedder")

TIMEOUT_SECONDS = 30
BATCH = 64
URL_SECRET = "embeddings_url"  # nosec B105 - the name of an org secret, not its value
MODEL_SECRET = "embeddings_model"  # nosec B105 - the name of an org secret, not its value
KEY_SECRET = "embeddings_api_key"  # nosec B105 - the name of an org secret, not its value
PREFIX_SECRET = "embeddings_query_prefix"  # nosec B105 - the name of an org secret, not its value


class EmbeddingError(RuntimeError):
    pass


EMBEDDINGS_LIMIT = "knowledge.embeddings_per_day"
limits.declare(
    EMBEDDINGS_LIMIT,
    "knowledge",
    "Texts embedded a day (knowledge and agent memory)",
    500_000,
    window="day",
    unit="texts",
    integrations=("embeddings",),
)


@dataclass(frozen=True)
class Embedder:
    url: str
    model: str
    api_key: str | None = None
    query_prefix: str = ""
    # An org's own service must stay on a public address; the deployment's may be on the private network
    public_only: bool = False
    # Called with the number of texts before each embed; raises when the org is over its limit
    meter: Callable[[int], None] | None = field(default=None, compare=False, repr=False)

    def embed(self, texts: list[str]) -> list[list[float]]:
        if self.meter is not None:
            self.meter(len(texts))
        vectors: list[list[float]] = []
        for start in range(0, len(texts), BATCH):
            vectors.extend(self._post(texts[start : start + BATCH]))
        return vectors

    def embed_query(self, text: str) -> list[float]:
        return self.embed([self.query_prefix + text])[0]

    def _post(self, batch: list[str]) -> list[list[float]]:
        headers = {"Authorization": f"Bearer {self.api_key}"} if self.api_key else {}
        if self.public_only:
            try:
                net.check_public(self.url)
            except ValueError as e:
                raise EmbeddingError(str(e)) from e
        try:
            response = requests.post(
                self.url.rstrip("/") + "/embeddings",
                json={"model": self.model, "input": batch},
                headers=headers,
                timeout=TIMEOUT_SECONDS,
                allow_redirects=False,
            )
            response.raise_for_status()
            rows = enumerate(response.json()["data"])
            data = [row for _, row in sorted(rows, key=lambda pair: pair[1].get("index", pair[0]))]
            vectors = [[float(x) for x in row["embedding"]] for row in data]
        except (requests.RequestException, ValueError, KeyError, TypeError) as e:
            logger.warning("embedding request failed: %s", e)
            raise EmbeddingError("The embedding service failed") from e
        if len(vectors) != len(batch):
            raise EmbeddingError("The embedding service returned the wrong number of vectors")
        return vectors


def configured() -> Embedder | None:
    """The deployment default from Doppler, or None."""
    url = os.environ.get("EMBEDDINGS_URL", "").strip()
    if not url:
        return None
    api_key = os.environ.get("EMBEDDINGS_API_KEY") or None
    if api_key is None and openrouter.is_openrouter(url):
        api_key = openrouter.deployment_key()
    return Embedder(
        url=url,
        model=os.environ.get("EMBEDDINGS_MODEL", "").strip() or "default",
        api_key=api_key,
        query_prefix=os.environ.get("EMBEDDINGS_QUERY_PREFIX", ""),
    )


def for_org(db, org_id: int) -> Embedder | None:
    """The org's own embeddings service, else the deployment default, else None. It counts against the org's limit."""

    def meter(count: int) -> None:
        limits.consume(db, org_id, EMBEDDINGS_LIMIT, count)

    saved = org_values(db, org_id, "embeddings")
    if saved is None:
        default = configured()
        # An embedder that is not an Embedder (a stand-in in tests) is used as it is, without the meter
        return replace(default, meter=meter) if isinstance(default, Embedder) else default
    api_key = saved.get(KEY_SECRET)
    if api_key is None and openrouter.is_openrouter(saved[URL_SECRET]):
        api_key = secrets.get_secret(db, org_id, openrouter.SECRET_NAME)
    return Embedder(
        url=saved[URL_SECRET],
        model=saved[MODEL_SECRET],
        api_key=api_key,
        query_prefix=saved.get(PREFIX_SECRET, ""),
        public_only=True,
        meter=meter,
    )


def _test(db, org_id: int) -> str:
    embedder = for_org(db, org_id)
    if embedder is None:
        raise IntegrationError("Set an embeddings service first")
    try:
        vector = embedder.embed(["test"])[0]
    except EmbeddingError as e:
        raise IntegrationError(str(e)) from e
    if len(vector) != DIMENSIONS:
        raise IntegrationError(f"{embedder.model} returns {len(vector)} dimensions. Platform stores {DIMENSIONS}.")
    return f"Connected. {embedder.model} returns {len(vector)} dimensions."


def _queue_reembed(org_id: int) -> None:
    """Embed the org's passages again with the service it saved. Passages already on its model are skipped."""
    from core.jobs import JobBusy, defer

    try:
        defer("knowledge.reembed", org_id=org_id)
    except JobBusy:
        logger.info("re-embed already queued org=%s", org_id)


register(
    Integration(
        key="embeddings",
        title="Embeddings",
        description="Connect an OpenAI-compatible embeddings service for meaning search.",
        fields=(
            Field(
                URL_SECRET,
                "Base URL",
                f"For example {openrouter.BASE_URL}, on a public address. Platform adds /embeddings.",
                kind="url",
                secret=False,
            ),
            Field(
                MODEL_SECRET,
                "Model",
                f"A model that returns {DIMENSIONS} numbers, such as Qwen3-Embedding-0.6B, or baai/bge-m3 on OpenRouter.",
                secret=False,
            ),
            Field(
                KEY_SECRET,
                "API key",
                "Leave empty when the service needs no key. For OpenRouter, empty uses the OpenRouter key.",
                optional=True,
            ),
            Field(
                PREFIX_SECRET,
                "Query prefix",
                "Text put before each search query. Qwen3-Embedding takes an instruction here.",
                secret=False,
                optional=True,
            ),
        ),
        docs="modules/knowledge",
        deployment=lambda: configured() is not None,
        test=_test,
        on_save=lambda db, org_id: _queue_reembed(org_id),
    )
)
use("embeddings", "knowledge")
use("embeddings", "agents")
use("openrouter", "knowledge")
use("openrouter", "agents")
