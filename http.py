import json
from typing import Any, Dict, Optional
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen


class ExternalServiceError(RuntimeError):
    """A public service could not return a usable response."""


def get_json(
    base_url: str,
    params: Optional[Dict[str, Any]] = None,
    headers: Optional[Dict[str, str]] = None,
    timeout: int = 12,
) -> Any:
    url = base_url
    if params:
        url = f"{base_url}?{urlencode(params)}"
    request_headers = {"User-Agent": "TorontoTravelAssistant/1.0"}
    if headers:
        request_headers.update(headers)
    request = Request(url, headers=request_headers)

    try:
        with urlopen(request, timeout=timeout) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except HTTPError as exc:
        raise ExternalServiceError(
            f"Service returned HTTP {exc.code}."
        ) from exc
    except URLError as exc:
        raise ExternalServiceError(
            f"Service request failed: {exc.reason}."
        ) from exc
    except json.JSONDecodeError as exc:
        raise ExternalServiceError(
            "Service returned invalid JSON."
        ) from exc

    if not isinstance(payload, (dict, list)):
        raise ExternalServiceError("Service returned an unexpected response.")
    return payload
