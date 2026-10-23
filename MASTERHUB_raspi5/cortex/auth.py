"""
cortex/auth.py
---------------
Cortex login / authorization / access-token lifecycle, built on top of
the generic cortex_client.CortexClient.

Cortex's authentication flow (see README.md -> "How to obtain Cortex
API credentials" for the account-side setup) is:

    1. requestAccess(clientId, clientSecret)
         The first time a given clientId is used, the user must
         approve it inside the EMOTIV Launcher/App. requestAccess
         reports whether that approval has already happened.
    2. authorize(clientId, clientSecret, license)
         Once access is granted, this exchanges the app credentials
         for a `cortexToken` -- the bearer token required by nearly
         every other Cortex method (createSession, subscribe, ...).

Cortex tokens don't carry a machine-readable expiry in the API
response, so this module treats them as valid for a conservative,
configurable TTL and transparently re-authorizes when that TTL elapses
or when the caller explicitly requests a refresh.
"""

from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Any, Optional

from cortex.config import CLIENT_ID, CLIENT_SECRET, LICENSE
from cortex.cortex_client import CortexClient, CortexRequestError
from cortex.logger import get_logger

log = get_logger("auth")

# Conservative soft TTL for a cortexToken before this module proactively
# re-authorizes, since Cortex does not return a machine-readable expiry.
# Well under Cortex's actual server-side session lifetime.
_TOKEN_SOFT_TTL_SECONDS = 6 * 60 * 60  # 6 hours


class CortexAuthError(Exception):
    """Raised when access has not been granted or authorization fails."""


@dataclass
class AuthCredentials:
    client_id: str = CLIENT_ID
    client_secret: str = CLIENT_SECRET
    license: str = LICENSE


class CortexAuth:
    """
    Handles the login/authorize/token-refresh lifecycle for one Cortex
    connection. One CortexAuth instance owns exactly one cortexToken.
    """

    def __init__(self, client: CortexClient, credentials: Optional[AuthCredentials] = None):
        self.client = client
        if credentials is None:
            from cortex.config import reload_credentials
            client_id, secret, license_key, _ = reload_credentials()
            credentials = AuthCredentials(client_id, secret, license_key)
        self.credentials = credentials
        self._token: Optional[str] = None
        self._token_fetched_at: float = 0.0

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def request_access(self) -> bool:
        """
        Ask Cortex whether this clientId/clientSecret pair has already
        been approved by the user in the EMOTIV Launcher/App.
        """
        if not self.credentials.client_id or not self.credentials.client_secret:
            raise CortexAuthError("CORTEX_CLIENT_ID and CORTEX_CLIENT_SECRET are missing. Please configure them in Connection Settings.")

        try:
            result = self.client.call(
                "requestAccess",
                {"clientId": self.credentials.client_id, "clientSecret": self.credentials.client_secret},
            )
        except CortexRequestError as exc:
            log.error(f"requestAccess failed: {exc}")
            raise CortexAuthError(f"requestAccess failed: {exc}") from exc

        granted = bool(result.get("accessGranted"))
        message = result.get("message", "")
        if granted:
            log.info("Cortex access already granted for this client")
        else:
            log.warning(f"Cortex access NOT yet granted: {message}")
            raise CortexAuthError(
                "Cortex access has not been granted for this CLIENT_ID. "
                "Open the EMOTIV Launcher/App, approve the access request "
                f"popup for this application, then retry. Cortex said: {message!r}"
            )
        return granted

    def authorize(self, debit: int = 0, force: bool = False) -> str:
        """
        Return a valid cortexToken, authorizing (or re-authorizing)
        with Cortex if there isn't a cached one, `force` is True, or the
        cached token has exceeded its soft TTL.

        `debit` is the number of Cortex "sessions" to pre-debit against
        a licensed session pool; 0 is correct for the free tier / most
        integrations (see Cortex API docs for licensed usage).
        """
        if not force and self._token and not self._is_token_stale():
            return self._token

        params: dict[str, Any] = {
            "clientId": self.credentials.client_id.strip(),
            "clientSecret": self.credentials.client_secret.strip(),
        }
        if self.credentials.license and str(self.credentials.license).strip():
            params["license"] = str(self.credentials.license).strip()
        if debit and int(debit) > 0:
            params["debit"] = int(debit)

        try:
            result = self.client.call("authorize", params)
        except CortexRequestError as exc:
            log.error(f"authorize failed: {exc}")
            raise CortexAuthError(f"authorize failed: {exc}") from exc

        token = result.get("cortexToken")
        if not token:
            raise CortexAuthError(f"authorize succeeded but returned no cortexToken: {result}")

        self._token = token
        self._token_fetched_at = time.monotonic()
        log.info("Authorized with Cortex; cortexToken acquired")
        return token

    def refresh_token(self) -> str:
        """Force re-authorization, discarding any cached token."""
        log.info("Refreshing cortexToken")
        return self.authorize(force=True)

    def clear_token(self) -> None:
        """Clear cached cortexToken."""
        self._token = None
        self._token_fetched_at = 0.0

    @property
    def token(self) -> Optional[str]:
        """The current cached token, if any (does not trigger a call)."""
        return self._token

    def login_and_authorize(self, force: bool = True) -> str:
        """
        Convenience helper covering the full flow: verify access has
        been granted, then authorize. Returns the cortexToken.
        """
        self.request_access()
        return self.authorize(force=force)

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _is_token_stale(self) -> bool:
        return (time.monotonic() - self._token_fetched_at) >= _TOKEN_SOFT_TTL_SECONDS
