"""数据库连接池模块

提供 SSH 隧道复用 + MySQL 连接池管理，适用于并发查询或高频数据库操作。
"""

import threading
import time
from queue import Queue, Empty
from typing import Optional, Dict, Any, List
from contextlib import contextmanager
from dataclasses import dataclass
from sshtunnel import SSHTunnelForwarder
import pymysql
from pymysql.cursors import DictCursor

from autotest.logging import get_logger
from autotest.exceptions import ConnectionException, QueryException

logger = get_logger(__name__)


@dataclass
class PoolConfig:
    """连接池配置"""
    min_connections: int = 2
    max_connections: int = 10
    connection_timeout: int = 30
    idle_timeout: int = 300
    max_lifetime: int = 3600
    health_check_interval: int = 60


class SSHTunnelManager:
    """SSH 隧道管理器 - 单例模式，同一个目标（跳板机 + DB 地址）复用一条隧道"""

    _instance: Optional["SSHTunnelManager"] = None
    _lock = threading.Lock()

    def __new__(cls):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        if self._initialized:
            return

        self._tunnels: Dict[str, SSHTunnelForwarder] = {}
        self._tunnel_locks: Dict[str, threading.Lock] = {}
        self._ref_counts: Dict[str, int] = {}
        self._lock = threading.Lock()
        self._initialized = True

        logger.info("SSH 隧道管理器初始化完成")

    def _get_tunnel_key(self, config: dict) -> str:
        return f"{config['jump_host_ip']}:{config['jump_host_port']}->{config['database_ip']}:{config['database_port']}"

    def get_tunnel(self, config: dict) -> SSHTunnelForwarder:
        tunnel_key = self._get_tunnel_key(config)

        with self._lock:
            if tunnel_key not in self._tunnel_locks:
                self._tunnel_locks[tunnel_key] = threading.Lock()

        with self._tunnel_locks[tunnel_key]:
            if tunnel_key in self._tunnels:
                tunnel = self._tunnels[tunnel_key]
                if tunnel.is_active:
                    self._ref_counts[tunnel_key] = self._ref_counts.get(tunnel_key, 0) + 1
                    logger.debug(f"复用 SSH 隧道: {tunnel_key}, 引用计数: {self._ref_counts[tunnel_key]}")
                    return tunnel
                else:
                    logger.warning(f"SSH 隧道已关闭，重新创建: {tunnel_key}")
                    del self._tunnels[tunnel_key]

            tunnel = SSHTunnelForwarder(
                (config["jump_host_ip"], config["jump_host_port"]),
                ssh_username=config["jump_host_user"],
                ssh_password=config["jump_host_password"],
                remote_bind_address=(config["database_ip"], config["database_port"]),
                set_keepalive=60,
            )
            tunnel.start()

            self._tunnels[tunnel_key] = tunnel
            self._ref_counts[tunnel_key] = 1
            logger.info(f"创建新 SSH 隧道: {tunnel_key}, 本地端口: {tunnel.local_bind_port}")

            return tunnel

    def release_tunnel(self, config: dict):
        tunnel_key = self._get_tunnel_key(config)
        with self._lock:
            if tunnel_key in self._ref_counts:
                self._ref_counts[tunnel_key] -= 1
                logger.debug(f"释放 SSH 隧道引用: {tunnel_key}, 剩余引用: {self._ref_counts[tunnel_key]}")

    def close_all(self):
        with self._lock:
            for tunnel_key, tunnel in self._tunnels.items():
                try:
                    tunnel.stop()
                    logger.info(f"关闭 SSH 隧道: {tunnel_key}")
                except Exception as e:
                    logger.error(f"关闭 SSH 隧道失败: {tunnel_key}, 错误: {e}")

            self._tunnels.clear()
            self._ref_counts.clear()


class PooledConnection:
    """池化连接包装器"""

    def __init__(self, connection: pymysql.Connection, created_at: float, pool: "ConnectionPool"):
        self.connection = connection
        self.created_at = created_at
        self.last_used_at = time.time()
        self._pool = pool
        self._in_use = True

    def is_expired(self, max_lifetime: int) -> bool:
        return time.time() - self.created_at > max_lifetime

    def is_idle_timeout(self, idle_timeout: int) -> bool:
        return time.time() - self.last_used_at > idle_timeout

    def is_healthy(self) -> bool:
        try:
            self.connection.ping(reconnect=False)
            return True
        except Exception:
            return False

    def release(self):
        if self._in_use:
            self._in_use = False
            self.last_used_at = time.time()
            self._pool._return_connection(self)


class ConnectionPool:
    """数据库连接池"""

    def __init__(self, config: dict, pool_config: PoolConfig = None):
        self.config = config
        self.pool_config = pool_config or PoolConfig()

        self._pool: Queue = Queue(maxsize=self.pool_config.max_connections)
        self._size = 0
        self._lock = threading.Lock()
        self._closed = False

        self._tunnel_manager = SSHTunnelManager()
        self._tunnel: Optional[SSHTunnelForwarder] = None

        self._health_check_thread: Optional[threading.Thread] = None
        self._stop_health_check = threading.Event()

        logger.info(f"连接池初始化: {config.get('database_name', 'unknown')}")

    def _ensure_tunnel(self) -> SSHTunnelForwarder:
        if self._tunnel is None or not self._tunnel.is_active:
            self._tunnel = self._tunnel_manager.get_tunnel(self.config)
        return self._tunnel

    def _create_connection(self) -> PooledConnection:
        tunnel = self._ensure_tunnel()

        conn = pymysql.connect(
            host="127.0.0.1",
            port=tunnel.local_bind_port,
            user=self.config["database_user"],
            password=self.config["database_password"],
            db=self.config["database_name"],
            charset="utf8mb4",
            cursorclass=DictCursor,
            autocommit=True,
            connect_timeout=self.pool_config.connection_timeout,
        )

        pooled_conn = PooledConnection(conn, time.time(), self)
        logger.debug(f"创建新数据库连接, 当前池大小: {self._size + 1}")
        return pooled_conn

    def get_connection(self) -> PooledConnection:
        if self._closed:
            raise ConnectionException("连接池已关闭")

        try:
            pooled_conn = self._pool.get_nowait()

            if pooled_conn.is_expired(self.pool_config.max_lifetime):
                logger.debug("连接已过期，关闭并创建新连接")
                self._close_connection(pooled_conn)
                return self._get_or_create_connection()

            if not pooled_conn.is_healthy():
                logger.debug("连接不健康，关闭并创建新连接")
                self._close_connection(pooled_conn)
                return self._get_or_create_connection()

            pooled_conn._in_use = True
            pooled_conn.last_used_at = time.time()
            return pooled_conn

        except Empty:
            return self._get_or_create_connection()

    def _get_or_create_connection(self) -> PooledConnection:
        with self._lock:
            if self._size < self.pool_config.max_connections:
                self._size += 1
                try:
                    return self._create_connection()
                except Exception as e:
                    self._size -= 1
                    raise ConnectionException(f"创建数据库连接失败: {e}")

        try:
            pooled_conn = self._pool.get(timeout=self.pool_config.connection_timeout)
            pooled_conn._in_use = True
            pooled_conn.last_used_at = time.time()
            return pooled_conn
        except Empty:
            raise ConnectionException(f"获取连接超时，池大小: {self._size}")

    def _return_connection(self, pooled_conn: PooledConnection):
        if self._closed:
            self._close_connection(pooled_conn)
            return

        if pooled_conn.is_expired(self.pool_config.max_lifetime) or not pooled_conn.is_healthy():
            self._close_connection(pooled_conn)
            return

        try:
            self._pool.put_nowait(pooled_conn)
        except Exception:
            self._close_connection(pooled_conn)

    def _close_connection(self, pooled_conn: PooledConnection):
        with self._lock:
            self._size -= 1

        try:
            pooled_conn.connection.close()
        except Exception as e:
            logger.warning(f"关闭连接时出错: {e}")

    @contextmanager
    def connection(self):
        """上下文管理器方式获取连接

        Usage:
            with pool.connection() as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT * FROM table")
        """
        pooled_conn = self.get_connection()
        try:
            yield pooled_conn.connection
        finally:
            pooled_conn.release()

    def execute(self, query: str, params: tuple = None) -> List[Dict[str, Any]]:
        """执行查询并返回结果（参数化，防止 SQL 注入）"""
        with self.connection() as conn:
            try:
                with conn.cursor() as cursor:
                    cursor.execute(query, params)
                    return cursor.fetchall()
            except Exception as e:
                raise QueryException(f"查询执行失败: {e}", query=query, params=params)

    def close(self):
        self._closed = True
        self._stop_health_check.set()

        while True:
            try:
                pooled_conn = self._pool.get_nowait()
                self._close_connection(pooled_conn)
            except Empty:
                break

        if self._tunnel:
            self._tunnel_manager.release_tunnel(self.config)

        logger.info(f"连接池已关闭: {self.config.get('database_name', 'unknown')}")

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()


class ConnectionPoolManager:
    """连接池管理器 - 按数据库复用连接池"""

    _instance: Optional["ConnectionPoolManager"] = None
    _lock = threading.Lock()

    def __new__(cls):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        if self._initialized:
            return

        self._pools: Dict[str, ConnectionPool] = {}
        self._pool_lock = threading.Lock()
        self._initialized = True

        logger.info("连接池管理器初始化完成")

    def _get_pool_key(self, config: dict) -> str:
        return f"{config['database_ip']}:{config['database_port']}/{config['database_name']}"

    def get_pool(self, config: dict, pool_config: PoolConfig = None) -> ConnectionPool:
        pool_key = self._get_pool_key(config)
        with self._pool_lock:
            if pool_key not in self._pools:
                self._pools[pool_key] = ConnectionPool(config, pool_config)
                logger.info(f"创建连接池: {pool_key}")
            return self._pools[pool_key]

    def close_all(self):
        with self._pool_lock:
            for pool_key, pool in self._pools.items():
                pool.close()
                logger.info(f"关闭连接池: {pool_key}")
            self._pools.clear()

        SSHTunnelManager().close_all()


_pool_manager = ConnectionPoolManager()


def get_pool(config: dict, pool_config: PoolConfig = None) -> ConnectionPool:
    """获取或创建连接池（便捷函数）"""
    return _pool_manager.get_pool(config, pool_config)


def close_all_pools():
    """关闭所有连接池（便捷函数）"""
    _pool_manager.close_all()
