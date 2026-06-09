"""API 路由模块"""

from .devices import router as devices_router
from .collector import router as collector_router
from .data import router as data_router
from .auth import router as auth_router
from .stats import router as stats_router
from .topology import router as topology_router
from .topology_visio import router as topology_visio_router

__all__ = ["devices_router", "collector_router", "data_router", "auth_router", "stats_router", "topology_router", "topology_visio_router"]
