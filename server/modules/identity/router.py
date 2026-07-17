from server.modules.identity.auth_router import router as auth_router
from server.modules.identity.profile_router import credentials_router
from server.modules.identity.profile_router import router as profile_router

routers = (auth_router, profile_router, credentials_router)

__all__ = ("routers",)
