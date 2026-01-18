"""
Model profile management for FlatAgents.

Provides centralized model configuration through profiles.yml files.
Profiles enable easy switching between model configurations (e.g., dev vs prod).

Resolution order (low to high priority):
1. default profile (fallback)
2. Named profile from agent's model field
3. Inline overrides from agent's model field
4. override profile (trumps all)
"""

import os
from typing import Any, Dict, Optional

from .monitoring import get_logger

logger = get_logger(__name__)

# Cache loaded profile managers by directory
_profile_managers: Dict[str, "ProfileManager"] = {}


class ProfileManager:
    """
    Manages model profiles from profiles.yml files.

    Resolution order (low to high priority):
    1. default profile (fallback)
    2. Named profile from agent's model field
    3. Inline overrides from agent's model field
    4. override profile (trumps all)

    Example:
        >>> manager = ProfileManager("config/profiles.yml")
        >>> config = manager.resolve_model_config("fast-cheap")
        >>> print(config)
        {'provider': 'cerebras', 'name': 'zai-glm-4.6', 'temperature': 0.6}
    """

    def __init__(self, profiles_file: Optional[str] = None):
        """
        Initialize profile manager.

        Args:
            profiles_file: Path to profiles.yml file (optional)
        """
        self.profiles_file = profiles_file
        self._profiles: Dict[str, Dict[str, Any]] = {}
        self._default_profile: Optional[str] = None
        self._override_profile: Optional[str] = None

        if profiles_file:
            self._load_profiles(profiles_file)

    @classmethod
    def get_instance(cls, config_dir: str) -> "ProfileManager":
        """
        Get or create a ProfileManager for a directory.

        Caches instances by directory to avoid re-reading profiles.yml.

        Args:
            config_dir: Directory containing profiles.yml

        Returns:
            ProfileManager instance (may have no profiles if file not found)
        """
        if config_dir not in _profile_managers:
            profiles_path = os.path.join(config_dir, "profiles.yml")
            if os.path.exists(profiles_path):
                _profile_managers[config_dir] = cls(profiles_path)
            else:
                # No profiles file - return empty manager
                _profile_managers[config_dir] = cls()
        return _profile_managers[config_dir]

    @classmethod
    def clear_cache(cls) -> None:
        """Clear cached ProfileManager instances."""
        _profile_managers.clear()

    def _load_profiles(self, profiles_file: str) -> None:
        """Load profiles from YAML file."""
        try:
            import yaml
        except ImportError:
            raise ImportError("pyyaml is required for profiles.yml")

        if not os.path.exists(profiles_file):
            logger.debug(f"No profiles file at {profiles_file}")
            return

        with open(profiles_file, 'r') as f:
            config = yaml.safe_load(f) or {}

        # Validate spec if present
        spec = config.get('spec')
        if spec and spec != 'flatprofiles':
            raise ValueError(f"Invalid profiles spec: expected 'flatprofiles', got '{spec}'")

        # Support both wrapped (spec/data) and unwrapped format
        data = config.get('data', config)

        self._profiles = data.get('model_profiles', {})
        self._default_profile = data.get('default')
        self._override_profile = data.get('override')

        logger.info(
            f"Loaded {len(self._profiles)} profiles from {profiles_file}"
            f" (default={self._default_profile}, override={self._override_profile})"
        )

    def get_profile(self, name: str) -> Optional[Dict[str, Any]]:
        """
        Get a profile by name.

        Args:
            name: Profile name

        Returns:
            Profile config dict or None if not found
        """
        return self._profiles.get(name)

    @property
    def profiles(self) -> Dict[str, Dict[str, Any]]:
        """All loaded profiles."""
        return self._profiles

    @property
    def default_profile(self) -> Optional[str]:
        """Name of the default profile."""
        return self._default_profile

    @property
    def override_profile(self) -> Optional[str]:
        """Name of the override profile."""
        return self._override_profile

    def resolve_model_config(
        self,
        agent_model_config: Any
    ) -> Dict[str, Any]:
        """
        Resolve the final model configuration.

        Resolution order:
        1. Start with default profile (if set)
        2. Apply named profile (if agent_model_config is string or has 'profile' key)
        3. Merge inline overrides (if agent_model_config is dict)
        4. Apply override profile (trumps all)

        Args:
            agent_model_config: Agent's model config (string, dict, or None)

        Returns:
            Fully resolved model configuration dict

        Raises:
            ValueError: If a referenced profile is not found
        """
        result = {}

        # 1. Apply default profile
        if self._default_profile:
            default_cfg = self.get_profile(self._default_profile)
            if default_cfg:
                result.update(default_cfg)
            else:
                logger.warning(f"Default profile '{self._default_profile}' not found")

        # 2. Handle agent's model config
        if isinstance(agent_model_config, str):
            # String = profile name
            profile_cfg = self.get_profile(agent_model_config)
            if profile_cfg:
                result.update(profile_cfg)
            else:
                raise ValueError(f"Model profile '{agent_model_config}' not found")

        elif isinstance(agent_model_config, dict):
            # Check for profile reference in dict
            profile_name = agent_model_config.get('profile')
            if profile_name:
                profile_cfg = self.get_profile(profile_name)
                if profile_cfg:
                    result.update(profile_cfg)
                else:
                    raise ValueError(f"Model profile '{profile_name}' not found")

            # Merge inline overrides (excluding 'profile' key)
            inline_overrides = {
                k: v for k, v in agent_model_config.items()
                if k != 'profile' and v is not None
            }
            result.update(inline_overrides)

        # 3. Apply override profile (trumps all)
        if self._override_profile:
            override_cfg = self.get_profile(self._override_profile)
            if override_cfg:
                result.update(override_cfg)
            else:
                logger.warning(f"Override profile '{self._override_profile}' not found")

        return result


def resolve_model_config(
    agent_model_config: Any,
    config_dir: str,
    profiles_file: Optional[str] = None
) -> Dict[str, Any]:
    """
    Convenience function to resolve model configuration.

    Args:
        agent_model_config: Agent's model config (string, dict, or None)
        config_dir: Directory containing agent config (for profiles.yml lookup)
        profiles_file: Explicit path to profiles.yml (overrides auto-discovery)

    Returns:
        Fully resolved model configuration dict

    Example:
        >>> config = resolve_model_config("fast-cheap", "./config")
        >>> print(config)
        {'provider': 'cerebras', 'name': 'zai-glm-4.6', 'temperature': 0.6}
    """
    if profiles_file:
        manager = ProfileManager(profiles_file)
    else:
        manager = ProfileManager.get_instance(config_dir)

    return manager.resolve_model_config(agent_model_config)


def discover_profiles_file(config_dir: str, explicit_path: Optional[str] = None) -> Optional[str]:
    """
    Discover profiles.yml in config_dir if not explicitly provided.

    This is used by FlatAgent and FlatMachine to auto-discover profiles.yml
    and propagate it to child agents/machines.

    Args:
        config_dir: Directory to search for profiles.yml
        explicit_path: Explicit path if already provided (returned as-is)

    Returns:
        Path to profiles.yml if found, explicit_path if provided, or None
    """
    if explicit_path:
        return explicit_path
    default_path = os.path.join(config_dir, 'profiles.yml')
    return default_path if os.path.exists(default_path) else None


__all__ = [
    "ProfileManager",
    "resolve_model_config",
    "discover_profiles_file",
]
