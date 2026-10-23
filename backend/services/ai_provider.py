"""Schema-validated A&R report providers, with an offline mock default."""
from __future__ import annotations

import json
import logging
import time
from typing import Protocol

import httpx

from ..config import settings
from ..core.errors import ApiError
from ..domain.schemas import ARReportPayload, EvidenceClaim

logger = logging.getLogger(__name__)
PROMPT_VERSION = "ar_report_v1"


class ReportProvider(Protocol):
    name: str
    model: str | None

    def generate(self, song_title: str, intelligence: dict) -> ARReportPayload: ...


class MockReportProvider:
    name = "mock"
    model = None

    def generate(self, song_title: str, intelligence: dict) -> ARReportPayload:
        features = intelligence["audio_features"]
        duration = features["duration_seconds"]["value"]
        claims: list[EvidenceClaim] = []
        if duration is not None:
            claims.append(
                EvidenceClaim(
                    claim=f"The uploaded recording was decoded successfully and measures {duration:.1f} seconds.",
                    evidence_refs=["audio_features.duration_seconds"],
                    kind="measured",
                )
            )
        estimated_features = [
            name for name, feature in features.items()
            if feature.get("status") == "estimated" and feature.get("value") is not None
        ]
        recommendations = []
        for feature_name in estimated_features:
            recommendations.append(
                EvidenceClaim(
                    claim=f"Review the estimated {feature_name.replace('_', ' ')} against your own listening before using it in release materials.",
                    evidence_refs=[f"audio_features.{feature_name}"],
                    kind="recommendation",
                )
            )
        if not recommendations:
            recommendations.append(
                EvidenceClaim(
                    claim="Add artist-supplied lyrics and review the track with a trusted listener to support more specific creative feedback.",
                    evidence_refs=[],
                    kind="recommendation",
                )
            )
        return ARReportPayload(
            summary=(
                f"Early A&R notes for “{song_title}” are limited to the uploaded audio file's "
                "validated measurements. No audience response or commercial outcome is inferred."
            ),
            strengths=claims,
            improvement_opportunities=[],
            hook_candidates=[],
            recommendations=recommendations,
            limitations=[
                *intelligence["limitations"],
                "This report is a prototype assessment and does not evaluate universal artistic quality.",
            ],
        )


class OpenRouterReportProvider:
    name = "openrouter"

    def __init__(self) -> None:
        self.model = settings.openrouter_model

    def generate(self, song_title: str, intelligence: dict) -> ARReportPayload:
        if not settings.openrouter_api_key or not settings.openrouter_model:
            raise ApiError(
                503,
                "AI_PROVIDER_UNAVAILABLE",
                "OpenRouter is selected but its server-side configuration is incomplete.",
            )
        provider_intelligence = dict(intelligence)
        provider_intelligence["lyrics_analysis"] = {
            "available": False,
            "status": "not_shared",
            "themes": [],
            "candidate_lines": [],
        }
        provider_intelligence["hook_candidates"] = [
            hook for hook in intelligence["hook_candidates"]
            if hook.get("kind") != "lyrical"
        ]
        context = {
            "song_title": song_title,
            "song_intelligence": provider_intelligence,
            "schema": ARReportPayload.model_json_schema(),
            "instructions": [
                "Use only the supplied data; do not infer missing lyrics, audience facts, or listener metrics.",
                "Every evidence reference must point to a supplied audio_features key.",
                "Separate measurement, interpretation, and recommendation.",
                "Do not promise streams, virality, revenue, or playlist placement.",
                "Return only a JSON object conforming to the supplied schema; do not include chain-of-thought.",
            ],
        }
        payload = {
            "model": settings.openrouter_model,
            "temperature": 0.2,
            "response_format": {"type": "json_object"},
            "messages": [
                {
                    "role": "system",
                    "content": "Generate concise evidence-grounded A&R decision support. Never invent evidence.",
                },
                {"role": "user", "content": json.dumps(context, ensure_ascii=False)},
            ],
        }
        endpoint = settings.openrouter_base_url.rstrip("/") + "/chat/completions"
        started = time.monotonic()
        response_text: str | None = None
        for attempt in range(settings.ai_provider_max_retries + 1):
            try:
                response = httpx.post(
                    endpoint,
                    headers={
                        "Authorization": f"Bearer {settings.openrouter_api_key}",
                        "Content-Type": "application/json",
                    },
                    json=payload,
                    timeout=settings.ai_provider_timeout_seconds,
                )
                if response.status_code == 429 or response.status_code >= 500:
                    if attempt < settings.ai_provider_max_retries:
                        time.sleep(min(0.5 * (2**attempt), 2))
                        continue
                response.raise_for_status()
                response_text = response.json()["choices"][0]["message"]["content"]
                break
            except (httpx.TimeoutException, httpx.NetworkError, httpx.HTTPStatusError, KeyError, IndexError, ValueError) as exc:
                if attempt < settings.ai_provider_max_retries and (
                    not isinstance(exc, httpx.HTTPStatusError)
                    or exc.response.status_code == 429
                    or exc.response.status_code >= 500
                ):
                    time.sleep(min(0.5 * (2**attempt), 2))
                    continue
                logger.warning(
                    "OpenRouter report request failed after %d attempt(s) in %.2fs",
                    attempt + 1,
                    time.monotonic() - started,
                )
                raise ApiError(
                    503,
                    "AI_PROVIDER_UNAVAILABLE",
                    "The report could not be generated with the configured provider.",
                ) from exc
        if response_text is None:
            raise ApiError(503, "AI_PROVIDER_UNAVAILABLE", "The configured report provider is unavailable.")
        try:
            parsed = json.loads(response_text)
            report = ARReportPayload.model_validate(parsed)
            available_refs = {
                f"audio_features.{name}"
                for name, feature in intelligence["audio_features"].items()
                if feature.get("value") is not None
            }
            claims = [
                *report.strengths,
                *report.improvement_opportunities,
                *report.hook_candidates,
                *report.recommendations,
            ]
            if any(ref not in available_refs for claim in claims for ref in claim.evidence_refs):
                raise ValueError("The report references unavailable evidence.")
        except (json.JSONDecodeError, ValueError, TypeError) as exc:
            logger.warning("OpenRouter returned an invalid A&R report schema.")
            raise ApiError(
                502,
                "AI_OUTPUT_INVALID",
                "The configured provider returned a report that failed validation.",
            ) from exc
        logger.info(
            "A&R report generated provider=openrouter model=%s elapsed_seconds=%.2f",
            settings.openrouter_model,
            time.monotonic() - started,
        )
        return report


def get_report_provider(*, allow_external: bool = False) -> ReportProvider:
    if settings.ai_provider == "openrouter":
        if allow_external:
            return OpenRouterReportProvider()
        return MockReportProvider()
    if settings.ai_provider == "mock":
        return MockReportProvider()
    raise ApiError(503, "AI_PROVIDER_UNAVAILABLE", "The configured report provider is not supported.")
