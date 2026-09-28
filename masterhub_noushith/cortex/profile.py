"""
cortex/profile.py
-----------------
Manages Emotiv trained profile querying and loading (setupProfile / queryProfile / getCurrentProfile)
via the Cortex JSON-RPC client.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from cortex.cortex_client import CortexClient, CortexRequestError
from cortex.logger import get_logger

log = get_logger("profile")


class ProfileError(Exception):
    """Raised when profile operations fail."""


@dataclass
class ProfileInfo:
    name: str
    loaded: bool = False


class ProfileManager:
    """Manages querying and loading Emotiv trained user profiles."""

    def __init__(self, client: CortexClient):
        self.client = client
        self.current_profile: Optional[str] = None
        self.available_profiles: list[str] = []

    def query_profiles(self, cortex_token: str) -> list[str]:
        """Query all available trained profiles registered under the user's Emotiv account."""
        try:
            result = self.client.call("queryProfile", {"cortexToken": cortex_token})
            profiles: list[str] = []
            if isinstance(result, list):
                for p in result:
                    if isinstance(p, dict):
                        name = p.get("name") or p.get("profileName") or ""
                        if name:
                            profiles.append(name)
                    elif isinstance(p, str):
                        profiles.append(p)
            self.available_profiles = profiles
            log.info(f"Queried {len(profiles)} Emotiv profiles: {profiles}")
            return profiles
        except CortexRequestError as exc:
            log.warning(f"queryProfile failed: {exc}")
            raise ProfileError(f"queryProfile failed: {exc}") from exc

    def get_current_profile(self, cortex_token: str, headset_id: str) -> Optional[str]:
        """Get the currently loaded profile on the given headset."""
        try:
            result = self.client.call(
                "getCurrentProfile",
                {"cortexToken": cortex_token, "headset": headset_id},
            )
            name = result.get("name") or result.get("profileName") if isinstance(result, dict) else None
            self.current_profile = name
            return name
        except Exception as exc:
            log.debug(f"getCurrentProfile failed: {exc}")
            self.current_profile = None
            return None

    def load_profile(self, cortex_token: str, headset_id: str, profile_name: str) -> bool:
        """Load an Emotiv trained profile onto the active headset session."""
        try:
            current = self.client.call('getCurrentProfile', {'cortexToken': cortex_token, 'headset': headset_id})
            name = current.get('name') if isinstance(current, dict) else None
            if name == profile_name:
                self.current_profile = name
                return True
            if name:
                if not current.get('loadedByThisApp'):
                    raise ProfileError('Unload the current profile in the EMOTIV application that loaded it first.')
                if not self.unload_profile(cortex_token, headset_id, name):
                    raise ProfileError('Could not unload the previous profile.')
            self.client.call(
                "setupProfile",
                {
                    "cortexToken": cortex_token,
                    "headset": headset_id,
                    "profile": profile_name,
                    "status": "load",
                },
            )
            self.current_profile = profile_name
            log.info(f"Loaded Emotiv trained profile '{profile_name}' for headset '{headset_id}'")
            return True
        except CortexRequestError as exc:
            log.error(f"setupProfile (load) failed for '{profile_name}': {exc}")
            raise ProfileError(f"setupProfile failed for '{profile_name}': {exc}") from exc

    def unload_profile(self, cortex_token: str, headset_id: str, profile_name: str) -> bool:
        """Unload active Emotiv trained profile."""
        try:
            self.client.call(
                "setupProfile",
                {
                    "cortexToken": cortex_token,
                    "headset": headset_id,
                    "profile": "",
                    "status": "unload",
                },
            )
            if self.current_profile == profile_name:
                self.current_profile = None
            log.info(f"Unloaded profile '{profile_name}'")
            return True
        except Exception as exc:
            log.warning(f"unload_profile failed: {exc}")
            return False
