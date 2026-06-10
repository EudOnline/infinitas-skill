# Cache management exports
from server.modules.discovery import cache as discovery_cache
from server.modules.discovery.router import router

__all__ = ["router", "discovery_cache"]
