"""Calling a provider's web API safely: timeouts, one retry, clear errors.

Both real providers (Cloudflare, OpenAI) use `post_json`. Rules:
  * every call has a timeout;
  * a timeout, a network problem, "429 too many requests" or a 5xx server error is retried ONCE
    (after a short pause; the provider's Retry-After header is respected up to a limit);
  * any other error status becomes a ProviderResponseError with a short, secret-free message;
  * a reply that is not JSON becomes a ProviderResponseError.
"""

import time

import httpx

from app.providers.base import ProviderResponseError, ProviderUnavailableError

MAX_RETRY_WAIT_SECONDS = 5.0
_RETRY_STATUS = {429, 500, 502, 503, 504}


def _wait_time(response: httpx.Response | None, default: float) -> float:
    if response is not None:
        retry_after = response.headers.get("retry-after", "")
        if retry_after.replace(".", "", 1).isdigit():
            return min(float(retry_after), MAX_RETRY_WAIT_SECONDS)
    return min(default, MAX_RETRY_WAIT_SECONDS)


def _short(text: str, limit: int = 200) -> str:
    text = " ".join(text.split())
    return text if len(text) <= limit else text[:limit] + "..."


def post_json(
    client: httpx.Client,
    url: str,
    *,
    headers: dict[str, str],
    body: dict,
    label: str,
    retries: int = 1,
    retry_delay: float = 1.0,
) -> dict:
    """POST `body` as JSON and return the JSON reply as a dict."""
    last_problem = "no answer"
    for attempt in range(retries + 1):
        response: httpx.Response | None = None
        try:
            response = client.post(url, headers=headers, json=body)
        except httpx.TimeoutException:
            last_problem = "it did not answer in time"
        except httpx.TransportError:
            last_problem = "the connection failed"
        else:
            if response.status_code in _RETRY_STATUS:
                last_problem = f"it answered with status {response.status_code}"
            elif response.status_code >= 400:
                raise ProviderResponseError(
                    f"{label} rejected the request (status {response.status_code}): "
                    f"{_error_text(response)}. {_hint(response.status_code)}"
                )
            else:
                try:
                    data = response.json()
                except ValueError as error:
                    raise ProviderResponseError(
                        f"{label} sent a reply that is not JSON."
                    ) from error
                if not isinstance(data, dict):
                    raise ProviderResponseError(f"{label} sent an unexpected reply.")
                return data
        if attempt < retries:
            time.sleep(_wait_time(response, retry_delay))
    raise ProviderUnavailableError(f"{label} is not available right now: {last_problem}.")


def _error_text(response: httpx.Response) -> str:
    try:
        data = response.json()
    except ValueError:
        return _short(response.text) or "no details"
    if isinstance(data, dict):
        errors = data.get("errors")
        if isinstance(errors, list) and errors:
            first = errors[0]
            return _short(
                str(first.get("message", first)) if isinstance(first, dict) else str(first)
            )
        error = data.get("error")
        if isinstance(error, dict) and error.get("message"):
            return _short(str(error["message"]))
        if isinstance(error, str):
            return _short(error)
    return _short(str(data))


def _hint(status: int) -> str:
    if status in (401, 403):
        return "Check that the API key or token is correct and has the right permissions."
    if status == 404:
        return "Check the account id and the model name."
    return ""
