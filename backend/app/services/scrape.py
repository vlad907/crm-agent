from __future__ import annotations

import logging
import re
import time

import httpx
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)

MAX_TEXT_LENGTH = 20_000
REQUEST_TIMEOUT = httpx.Timeout(connect=5.0, read=10.0, write=10.0, pool=5.0)
RETRY_ATTEMPTS = 2
RETRY_BACKOFF_SECONDS = 0.25
USER_AGENT = "crm-agent/1.0 (+https://example.local)"


class WebsiteFetchError(RuntimeError):
    pass


def fetch_html(url: str) -> str:
    logger.info("Website fetch start url=%s", url)
    headers = {"User-Agent": USER_AGENT}
    last_error: Exception | None = None

    for attempt in range(RETRY_ATTEMPTS + 1):
        try:
            with httpx.Client(timeout=REQUEST_TIMEOUT, follow_redirects=True, headers=headers) as client:
                response = client.get(url)
                response.raise_for_status()
                logger.info(
                    "Website fetch end url=%s status=%s bytes=%s",
                    url,
                    response.status_code,
                    len(response.content),
                )
                return response.text
        except httpx.HTTPStatusError as exc:
            status_code = exc.response.status_code
            message = f"HTTP {status_code} ({exc.response.reason_phrase})"
            logger.warning("Website fetch failed url=%s attempt=%s error=%s", url, attempt + 1, message)
            if status_code >= 500 and attempt < RETRY_ATTEMPTS:
                time.sleep(RETRY_BACKOFF_SECONDS * (attempt + 1))
                continue
            logger.info("Website fetch end url=%s status=failed", url)
            raise WebsiteFetchError(message) from exc
        except httpx.TimeoutException as exc:
            last_error = exc
            logger.warning(
                "Website fetch timeout url=%s attempt=%s error=%s",
                url,
                attempt + 1,
                exc,
            )
            if attempt < RETRY_ATTEMPTS:
                time.sleep(RETRY_BACKOFF_SECONDS * (attempt + 1))
                continue
            logger.info("Website fetch end url=%s status=failed", url)
            raise WebsiteFetchError("Request timed out") from exc
        except httpx.RequestError as exc:
            last_error = exc
            logger.warning(
                "Website fetch request error url=%s attempt=%s error=%s",
                url,
                attempt + 1,
                exc,
            )
            if attempt < RETRY_ATTEMPTS:
                time.sleep(RETRY_BACKOFF_SECONDS * (attempt + 1))
                continue
            logger.info("Website fetch end url=%s status=failed", url)
            raise WebsiteFetchError(f"Network error: {exc}") from exc

    if last_error is not None:
        logger.info("Website fetch end url=%s status=failed", url)
        raise WebsiteFetchError(str(last_error)) from last_error
    logger.info("Website fetch end url=%s status=failed", url)
    raise WebsiteFetchError("Unknown fetch error")


def extract_text(html: str, *, max_length: int = MAX_TEXT_LENGTH) -> str:
    try:
        soup = BeautifulSoup(html, "html.parser")
        for tag in soup(["script", "style", "nav", "footer", "header"]):
            tag.decompose()
        text = soup.get_text(separator=" ", strip=True)
    except Exception:
        logger.exception("Website HTML parse failed")
        return ""

    normalized = re.sub(r"\s+", " ", text).strip()
    if len(normalized) > max_length:
        return normalized[:max_length]
    return normalized
