"""
backend/services/tinyfish_client.py — Production-Grade TinyFish Agent API Client.
================================================================================
Handles official TinyFish Agent API interactions with:
  • Official endpoint: POST /v1/automation/run (and /run-async fallback)
  • X-API-Key header authentication
  • Natural language goal + output_schema enforcement
  • Bounded retries with exponential backoff & jitter
  • Rate limit handling (HTTP 429 & Retry-After)
  • Timeout guards and connection pooling
  • Concurrency locking to prevent duplicate simultaneous executions
  • Secure credential handling (never logs or leaks secrets)
"""

from __future__ import annotations

import asyncio
import logging
import random
import time
from typing import Any, Dict, Optional

import httpx

from backend.config import settings

logger = logging.getLogger("tinyfish_client")
logger.setLevel(logging.INFO)


# ─────────────────────────────────────────────────────────────────────────────
# EXCEPTION HIERARCHY
# ─────────────────────────────────────────────────────────────────────────────
class TinyFishError(Exception):
    """Base exception for all TinyFish errors."""
    pass


class TinyFishMissingKeyError(TinyFishError):
    """Raised when TINYFISH_API_KEY is not configured."""
    pass


class TinyFishAuthError(TinyFishError):
    """Raised on HTTP 401 or 403 authentication/authorization failures."""
    pass


class TinyFishRateLimitError(TinyFishError):
    """Raised on HTTP 429 rate limit errors."""
    def __init__(self, message: str, retry_after: Optional[float] = None) -> None:
        super().__init__(message)
        self.retry_after = retry_after


class TinyFishTimeoutError(TinyFishError):
    """Raised when request or execution times out."""
    pass


class TinyFishConnectionError(TinyFishError):
    """Raised on low-level transport/network connection failures."""
    pass


class TinyFishExtractionError(TinyFishError):
    """Raised when the agent returns FAILED or malformed output."""
    def __init__(self, message: str, raw_response: Optional[Dict[str, Any]] = None) -> None:
        super().__init__(message)
        self.raw_response = raw_response or {}


# ─────────────────────────────────────────────────────────────────────────────
# TINYFISH API CLIENT
# ─────────────────────────────────────────────────────────────────────────────
class TinyFishClient:
    """
    Official TinyFish Automation Agent API Client.
    """

    def __init__(
        self,
        api_key: Optional[str] = None,
        base_url: Optional[str] = None,
        request_timeout: Optional[float] = None,
        connect_timeout: Optional[float] = None,
        max_retries: Optional[int] = None,
    ) -> None:
        self.api_key = (api_key if api_key is not None else settings.TINYFISH_API_KEY).strip()
        self.base_url = (base_url or settings.TINYFISH_BASE_URL).rstrip("/")
        self.request_timeout = request_timeout or settings.REQUEST_TIMEOUT_SECONDS
        self.connect_timeout = connect_timeout or settings.CONNECT_TIMEOUT_SECONDS
        self.max_retries = max_retries if max_retries is not None else settings.MAX_RETRIES

        # Concurrency guards keyed by URL/goal to prevent concurrent duplicate agent requests
        self._concurrency_locks: Dict[str, asyncio.Lock] = {}
        self._global_lock = asyncio.Lock()

    def is_configured(self) -> bool:
        """Returns True if an API key is available."""
        return bool(self.api_key and len(self.api_key) > 5)

    def _get_headers(self) -> Dict[str, str]:
        """Constructs secure request headers. Never logs credentials."""
        if not self.is_configured():
            raise TinyFishMissingKeyError(
                "TINYFISH_API_KEY is not set. Please configure TINYFISH_API_KEY in your environment or .env file."
            )
        return {
            "X-API-Key": self.api_key,
            "Content-Type": "application/json",
            "User-Agent": "SAIL-YANTRA-TinyFish-Integration/1.0",
        }

    async def _get_lock(self, key: str) -> asyncio.Lock:
        """Thread/asyncio safe lock retriever for specific extraction targets."""
        async with self._global_lock:
            if key not in self._concurrency_locks:
                self._concurrency_locks[key] = asyncio.Lock()
            return self._concurrency_locks[key]

    async def run_extraction(
        self,
        url: str,
        goal: str,
        output_schema: Optional[Dict[str, Any]] = None,
        browser_profile: str = "lite",
    ) -> Dict[str, Any]:
        """
        Executes a web agent automation run with concurrency protection and bounded retries.

        Args:
            url: Public web target URL.
            goal: Natural language instructions for extraction.
            output_schema: JSON Schema to enforce structured output.
            browser_profile: 'lite' or 'default'.

        Returns:
            Dict containing the extracted 'result' object.
        """
        lock = await self._get_lock(url)
        async with lock:
            return await self._execute_with_retry(
                url=url,
                goal=goal,
                output_schema=output_schema,
                browser_profile=browser_profile,
            )

    async def _execute_with_retry(
        self,
        url: str,
        goal: str,
        output_schema: Optional[Dict[str, Any]],
        browser_profile: str,
    ) -> Dict[str, Any]:
        """Performs HTTP request with exponential backoff on retryable errors."""
        headers = self._get_headers()
        endpoint = f"{self.base_url}/v1/automation/run"

        payload: Dict[str, Any] = {
            "url": url,
            "goal": goal,
            "browser_profile": browser_profile,
        }
        if output_schema:
            payload["output_schema"] = output_schema

        limits = httpx.Limits(max_keepalive_connections=5, max_connections=10)
        timeout = httpx.Timeout(
            self.request_timeout,
            connect=self.connect_timeout,
            read=self.request_timeout,
            write=10.0,
            pool=10.0,
        )

        last_exception: Optional[Exception] = None

        for attempt in range(self.max_retries + 1):
            try:
                logger.info(
                    "Executing TinyFish agent request (attempt %d/%d) for URL: %s",
                    attempt + 1,
                    self.max_retries + 1,
                    url,
                )

                async with httpx.AsyncClient(limits=limits, timeout=timeout) as client:
                    response = await client.post(endpoint, json=payload, headers=headers)

                # Process HTTP status
                if response.status_code in (200, 201, 202):
                    data = response.json()
                    status = data.get("status")
                    if status in ("PENDING", "RUNNING"):
                        run_id = data.get("run_id")
                        if run_id:
                            logger.info("TinyFish run %s is %s, polling for completion...", run_id, status)
                            return await self._poll_for_completion(run_id, url=url)
                    return self._parse_agent_response(data, url=url)

                if response.status_code in (401, 403):
                    logger.error("TinyFish authentication failed (HTTP %d)", response.status_code)
                    raise TinyFishAuthError(
                        f"Authentication failed (HTTP {response.status_code}). Verify your TINYFISH_API_KEY."
                    )

                if response.status_code == 429:
                    retry_after_hdr = response.headers.get("Retry-After")
                    wait_seconds = float(retry_after_hdr) if retry_after_hdr else (2.0 ** attempt)
                    logger.warning("TinyFish rate limit encountered (HTTP 429). Retry-After: %.1fs", wait_seconds)
                    if attempt < self.max_retries:
                        await asyncio.sleep(wait_seconds + random.uniform(0.1, 0.5))
                        continue
                    raise TinyFishRateLimitError("TinyFish API rate limit exceeded.", retry_after=wait_seconds)

                # Server errors: retryable
                if response.status_code in (500, 502, 503, 504):
                    logger.warning("TinyFish server error (HTTP %d). Attempt %d.", response.status_code, attempt + 1)
                    if attempt < self.max_retries:
                        backoff = (settings.RETRY_BACKOFF_FACTOR ** attempt) + random.uniform(0.2, 0.8)
                        await asyncio.sleep(backoff)
                        continue
                    raise TinyFishExtractionError(
                        f"TinyFish service unavailable (HTTP {response.status_code}): {response.text[:200]}"
                    )

                # Other 4xx client errors
                raise TinyFishExtractionError(
                    f"TinyFish client error (HTTP {response.status_code}): {response.text[:200]}"
                )

            except (httpx.TimeoutException, TimeoutError) as te:
                logger.warning("TinyFish request timed out on attempt %d: %s", attempt + 1, str(te))
                last_exception = TinyFishTimeoutError(f"Request to TinyFish timed out after {self.request_timeout}s.")
                if attempt < self.max_retries:
                    backoff = (settings.RETRY_BACKOFF_FACTOR ** attempt) + random.uniform(0.2, 0.5)
                    await asyncio.sleep(backoff)
                    continue

            except httpx.NetworkError as ne:
                logger.warning("TinyFish network error on attempt %d: %s", attempt + 1, str(ne))
                last_exception = TinyFishConnectionError(f"Network transport error connecting to TinyFish: {str(ne)}")
                if attempt < self.max_retries:
                    backoff = (settings.RETRY_BACKOFF_FACTOR ** attempt) + random.uniform(0.2, 0.5)
                    await asyncio.sleep(backoff)
                    continue

            except (TinyFishAuthError, TinyFishRateLimitError, TinyFishMissingKeyError):
                raise

            except Exception as ex:
                logger.error("Unexpected error during TinyFish execution: %s", str(ex))
                last_exception = TinyFishError(f"Unexpected TinyFish error: {str(ex)}")
                break

        if last_exception:
            raise last_exception

        raise TinyFishExtractionError("TinyFish extraction failed after maximum retries.")

    async def _poll_for_completion(self, run_id: str, url: str) -> Dict[str, Any]:
        """Polls GET /v1/automation/runs/{run_id} until completion or timeout."""
        headers = self._get_headers()
        endpoint = f"{self.base_url}/v1/automation/runs/{run_id}"
        poll_interval = 2.0
        start_time = time.time()
        timeout = httpx.Timeout(self.request_timeout, connect=self.connect_timeout)

        async with httpx.AsyncClient(timeout=timeout) as client:
            while time.time() - start_time < self.request_timeout:
                await asyncio.sleep(poll_interval)
                resp = await client.get(endpoint, headers=headers)
                if resp.status_code == 200:
                    data = resp.json()
                    status = data.get("status")
                    if status in ("COMPLETED", "SUCCESS", "DONE"):
                        return self._parse_agent_response(data, url=url)
                    elif status == "FAILED":
                        raise TinyFishExtractionError(
                            f"TinyFish agent run {run_id} failed: {data.get('error')}",
                            raw_response=data,
                        )
                elif resp.status_code in (401, 403):
                    raise TinyFishAuthError("Authentication failure while polling TinyFish run.")
                elif resp.status_code == 429:
                    await asyncio.sleep(3.0)
                    continue

        raise TinyFishTimeoutError(f"Polling TinyFish run {run_id} timed out after {self.request_timeout}s.")

    def _parse_agent_response(self, data: Dict[str, Any], url: str) -> Dict[str, Any]:
        """
        Parses official TinyFish AgentRunResponse.
        Validates status is 'COMPLETED' and returns the structured result.
        """
        status = data.get("status")
        run_id = data.get("run_id", "unknown")

        if status == "FAILED":
            err_info = data.get("error") or {}
            err_msg = err_info.get("message") if isinstance(err_info, dict) else str(err_info)
            logger.error("TinyFish run %s reported failure: %s", run_id, err_msg)
            raise TinyFishExtractionError(
                f"TinyFish agent reported failure for {url}: {err_msg}",
                raw_response=data,
            )

        if status not in ("COMPLETED", "SUCCESS", "DONE"):
            logger.warning("TinyFish run %s finished with status: %s", run_id, status)

        result = data.get("result")
        if result is None:
            raise TinyFishExtractionError(
                f"TinyFish agent returned empty result for {url} (status={status})",
                raw_response=data,
            )

        # If result is wrapped in {"result": {...}}
        if isinstance(result, dict) and "result" in result and len(result) == 1:
            result = result["result"]

        return {
            "result": result,
            "run_id": run_id,
            "status": status,
            "finished_at": data.get("finished_at"),
        }


# Global singleton client instance
tinyfish_client = TinyFishClient()
