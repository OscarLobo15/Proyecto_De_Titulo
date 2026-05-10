import logging
import time
from typing import Any, Optional
from urllib.parse import urlparse

import httpx

from app.config import settings

logger = logging.getLogger(__name__)


class AIConfigurationError(RuntimeError):
    pass


class AIRemoteServiceError(RuntimeError):
    pass


class RemoteLLMClient:
    def __init__(
        self,
        base_url: Optional[str] = None,
        endpoint: Optional[str] = None,
        timeout_seconds: Optional[float] = None,
        retries: Optional[int] = None,
        retry_delay_seconds: Optional[float] = None,
    ) -> None:
        self.base_url = (base_url or settings.ai_server_url or "").rstrip("/")
        self.endpoint = endpoint or settings.ai_generate_endpoint
        self.timeout_seconds = timeout_seconds or settings.ai_timeout_seconds
        self.retries = settings.ai_request_retries if retries is None else retries
        self.retry_delay_seconds = (
            settings.ai_request_retry_delay_seconds if retry_delay_seconds is None else retry_delay_seconds
        )

    @property
    def url(self) -> str:
        if not self.base_url:
            raise AIConfigurationError("Falta configurar AI_SERVER_URL.")
        endpoint = self.endpoint if self.endpoint.startswith("/") else f"/{self.endpoint}"
        if urlparse(self.base_url).path.rstrip("/") == endpoint.rstrip("/"):
            return self.base_url
        return f"{self.base_url}{endpoint}"

    def generate(self, prompt: str) -> str:
        attempts = self.retries + 1
        last_error: Optional[Exception] = None

        for attempt in range(1, attempts + 1):
            try:
                logger.info("Calling remote AI service at %s (attempt %s/%s)", self.url, attempt, attempts)
                with httpx.Client(timeout=self.timeout_seconds) as client:
                    response = client.post(self.url, json={"prompt": prompt})
                    response.raise_for_status()
                return self._parse_response(response)
            except httpx.TimeoutException as exc:
                last_error = exc
                logger.warning("Remote AI service timeout after %s seconds on attempt %s/%s", self.timeout_seconds, attempt, attempts)
            except httpx.HTTPStatusError as exc:
                last_error = exc
                status_code = exc.response.status_code
                logger.warning("Remote AI service returned HTTP %s on attempt %s/%s", status_code, attempt, attempts)
                if not _should_retry_status(status_code):
                    raise AIRemoteServiceError(f"El servidor IA respondio con HTTP {status_code}.") from exc
            except httpx.RequestError as exc:
                last_error = exc
                logger.warning("Remote AI service request failed on attempt %s/%s: %s", attempt, attempts, exc)
            except ValueError as exc:
                last_error = exc
                logger.warning("Remote AI service returned an invalid envelope on attempt %s/%s: %s", attempt, attempts, exc)

            if attempt < attempts:
                time.sleep(self.retry_delay_seconds)

        raise AIRemoteServiceError(
            "El servidor IA remoto no respondio correctamente despues de varios intentos. "
            "Revisa que el PC remoto, el tunel Cloudflare y el endpoint del modelo esten activos."
        ) from last_error

    def _parse_response(self, response: httpx.Response) -> str:
        try:
            payload: dict[str, Any] = response.json()
        except ValueError as exc:
            raise ValueError("JSON invalido") from exc

        model_response = payload.get("response")
        if not isinstance(model_response, str) or not model_response.strip():
            raise ValueError("falta el campo response")

        return model_response.strip()


def _should_retry_status(status_code: int) -> bool:
    return status_code in {408, 409, 425, 429} or status_code >= 500
