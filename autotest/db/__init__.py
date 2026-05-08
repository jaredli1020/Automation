"""数据库模块 - SSH 隧道 + 连接池

- JumpHostDatabaseConnector：简单连接器，每次查询重建隧道（低频场景）
- ConnectionPool：连接池，SSH 隧道复用 + MySQL 连接复用（高频/并发场景）

业务项目自行按需定义数据库实例：

    from autotest.db import JumpHostDatabaseConnector, create_db_config

    db_config = create_db_config(
        database_ip="10.0.0.1",
        database_name="my_db",
    )
    my_db = JumpHostDatabaseConnector(db_config)
"""

from .connector import (
    JumpHostDatabaseConnector,
    create_db_config,
    get_env,
)
from .connection_pool import (
    PoolConfig,
    SSHTunnelManager,
    PooledConnection,
    ConnectionPool,
    ConnectionPoolManager,
    get_pool,
    close_all_pools,
)

__all__ = [
    "JumpHostDatabaseConnector",
    "create_db_config",
    "get_env",
    "PoolConfig",
    "SSHTunnelManager",
    "PooledConnection",
    "ConnectionPool",
    "ConnectionPoolManager",
    "get_pool",
    "close_all_pools",
]
