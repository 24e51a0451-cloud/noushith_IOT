"""
cortex/session.py
-------------------
Cortex session lifecycle: create, activate, close, and recover a
session after a reconnect. A Cortex "session" ties a specific headset
to a specific cortexToken and is required before subscribing to any
data stream (see stream.py).

Cortex methods used:
    createSession   -- open (and optionally activate) a session for a headset
    updateSession   -- change an existing session's status ("active"/"close")
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from cortex.config import SESSION_STATUS
from cortex.cortex_client import CortexClient, CortexRequestError
from cortex.logger import get_logger

log = get_logger("session")


class SessionError(Exception):
    """Raised when a session cannot be created, activated, closed, or recovered."""


@dataclass
class SessionInfo:
    id: str
    headset_id: str
    status: str
    raw: dict


class SessionManager:
    def __init__(self, client: CortexClient):
        self.client = client
        self._current: Optional[SessionInfo] = None

    @property
    def current(self) -> Optional[SessionInfo]:
        return self._current

    # ------------------------------------------------------------------
    # Create / activate / close
    # ------------------------------------------------------------------

    def create_session(self, cortex_token: str, headset_id: str, activate: bool = True) -> SessionInfo:
        """
        Create a new session for `headset_id`. If `activate` is True
        (the default), the session uses the configured SESSION_STATUS;
        otherwise it's created "open". Mental commands ("com") and device
        diagnostics ("dev") do not require activation. Activation is for
        licensed features such as raw EEG, recording, and high-resolution
        performance metrics, and may consume session quota.
        If a session conflict or stale session exists, queries and closes stale sessions first.
        """
        status = SESSION_STATUS if activate else "open"
        try:
            result = self.client.call(
                "createSession",
                {"cortexToken": cortex_token, "headset": headset_id, "status": status},
            )
        except CortexRequestError as exc:
            err_msg = str(exc).lower()
            if "already" in err_msg or "in use" in err_msg or "being used" in err_msg or exc.code in (-32002, 102):
                log.warning(f"Session conflict for headset '{headset_id}': {exc}. Attempting to query and resolve stale sessions...")
                try:
                    existing = self.client.call("querySessions", {"cortexToken": cortex_token})
                    if isinstance(existing, list):
                        for s in existing:
                            s_id = s.get("id")
                            s_hs = s.get("headset", {}).get("id", "") if isinstance(s.get("headset"), dict) else s.get("headset", "")
                            if s_hs == headset_id and s_id:
                                log.info(f"Closing stale session '{s_id}' for headset '{headset_id}'")
                                try:
                                    self.client.call("updateSession", {"cortexToken": cortex_token, "session": s_id, "status": "close"})
                                except Exception:
                                    pass
                    # Retry session creation after cleanup
                    result = self.client.call(
                        "createSession",
                        {"cortexToken": cortex_token, "headset": headset_id, "status": status},
                    )
                except Exception as retry_exc:
                    log.error(f"createSession retry failed for headset '{headset_id}': {retry_exc}")
                    raise SessionError(f"createSession failed for headset '{headset_id}': {retry_exc}") from retry_exc
            else:
                log.error(f"createSession failed for headset '{headset_id}': {exc}")
                raise SessionError(f"createSession failed for headset '{headset_id}': {exc}") from exc

        session = SessionInfo(
            id=result.get("id", ""),
            headset_id=headset_id,
            status=result.get("status", status),
            raw=result,
        )
        if not session.id:
            raise SessionError(f"createSession succeeded but returned no session id: {result}")

        self._current = session
        log.info(f"Created session '{session.id}' for headset '{headset_id}' (status={session.status})")
        return session

    def activate_session(self, cortex_token: str, session_id: Optional[str] = None) -> SessionInfo:
        session_id = session_id or self._require_current_id()
        try:
            result = self.client.call(
                "updateSession",
                {"cortexToken": cortex_token, "session": session_id, "status": "active"},
            )
        except CortexRequestError as exc:
            log.error(f"activate_session failed for '{session_id}': {exc}")
            raise SessionError(f"activate_session failed for '{session_id}': {exc}") from exc

        headset_id = self._current.headset_id if self._current else result.get("headset", "")
        session = SessionInfo(id=result.get("id", session_id), headset_id=headset_id, status=result.get("status", "active"), raw=result)
        self._current = session
        log.info(f"Activated session '{session.id}'")
        return session

    def close_session(self, cortex_token: str, session_id: Optional[str] = None) -> None:
        session_id = session_id or (self._current.id if self._current else None)
        if not session_id:
            log.debug("close_session called with no active session; nothing to do")
            return

        try:
            self.client.call(
                "updateSession",
                {"cortexToken": cortex_token, "session": session_id, "status": "close"},
            )
            log.info(f"Closed session '{session_id}'")
        except CortexRequestError as exc:
            # A session that's already gone (e.g. the headset dropped)
            # is not a fatal error for our purposes -- log and move on.
            log.warning(f"close_session for '{session_id}' reported an error (may already be closed): {exc}")
        finally:
            if self._current and self._current.id == session_id:
                self._current = None

    # ------------------------------------------------------------------
    # Recovery after reconnect
    # ------------------------------------------------------------------

    def recover_session(self, cortex_token: str, headset_id: str) -> SessionInfo:
        """
        Re-establish a usable session after a WebSocket reconnect. The
        cortexToken is necessarily new (tokens don't survive a
        reconnect's re-authorization), so any previous session id is no
        longer guaranteed valid. This best-effort-closes whatever
        session id we last knew about (ignoring failures, since it may
        already be gone) and then creates a fresh active session.
        """
        stale_id = self._current.id if self._current else None
        if stale_id:
            log.info(f"Recovering session: closing stale session '{stale_id}' before recreating")
            self.close_session(cortex_token, stale_id)

        return self.create_session(cortex_token, headset_id, activate=True)

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _require_current_id(self) -> str:
        if self._current is None:
            raise SessionError("No current session; call create_session() first")
        return self._current.id
