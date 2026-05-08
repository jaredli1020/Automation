"""数据库连接器模块

提供基于 SSH 隧道的 MySQL 数据库连接，支持跳板机访问。
配置通过 create_db_config() 或直接传入字典，不依赖特定业务。
"""

import os
from typing import Optional
from sshtunnel import SSHTunnelForwarder
import pymysql


def get_env(key: str, default: str = None, required: bool = False) -> Optional[str]:
    """获取环境变量"""
    value = os.getenv(key, default)
    if required and value is None:
        raise ValueError(f"环境变量 {key} 未设置")
    return value


class JumpHostDatabaseConnector:
    """通过 SSH 跳板机连接 MySQL 数据库

    不维护长连接，每次查询创建独立隧道和连接。适合低频查询，
    高频场景请使用 ConnectionPool。
    """

    def __init__(self, config: dict):
        """
        Args:
            config: 数据库配置字典，包含以下字段：
                jump_host_ip / jump_host_port / jump_host_user / jump_host_password
                database_ip / database_port / database_user / database_password / database_name
        """
        self.config = config

    def connect_to_jump_host(self):
        server = SSHTunnelForwarder(
            (self.config["jump_host_ip"], self.config["jump_host_port"]),
            ssh_username=self.config["jump_host_user"],
            ssh_password=self.config["jump_host_password"],
            remote_bind_address=(self.config["database_ip"], self.config["database_port"]),
        )
        server.start()
        return server

    def connect_to_database(self, server):
        conn = pymysql.connect(
            host="127.0.0.1",
            port=server.local_bind_port,
            user=self.config["database_user"],
            password=self.config["database_password"],
            db=self.config["database_name"],
        )
        return conn

    def query_params(self, query: str, params=None):
        """执行参数化查询（推荐，防止 SQL 注入）"""
        with self.connect_to_jump_host() as server:
            with self.connect_to_database(server) as conn:
                with conn.cursor() as cursor:
                    cursor.execute(query, params)
                    return cursor.fetchall()

    def query_database_select_field_names(self, query, params=None):
        """执行查询并返回字段名和结果"""
        with self.connect_to_jump_host() as server:
            with self.connect_to_database(server) as conn:
                with conn.cursor() as cursor:
                    cursor.execute(query, params)
                    results = cursor.fetchall()
                    field_names = [desc[0] for desc in cursor.description]
                    return {"field_names": field_names, "results": results}


def create_db_config(database_ip: str, database_name: str,
                     database_user: str = None, database_password: str = None,
                     database_port: int = 3306,
                     jump_host_ip: str = None, jump_host_port: int = None,
                     jump_host_user: str = None, jump_host_password: str = None) -> dict:
    """创建数据库配置字典。

    跳板机字段若不传入，则从环境变量 JUMP_HOST_* 读取。
    """
    return {
        "jump_host_ip": jump_host_ip or get_env("JUMP_HOST_IP", required=True),
        "jump_host_port": jump_host_port or int(get_env("JUMP_HOST_PORT", "2222")),
        "jump_host_user": jump_host_user or get_env("JUMP_HOST_USER", required=True),
        "jump_host_password": jump_host_password or get_env("JUMP_HOST_PASSWORD", required=True),
        "database_ip": database_ip,
        "database_port": database_port,
        "database_user": database_user or get_env("DB_DEFAULT_USER", "readonly"),
        "database_password": database_password or get_env("DB_DEFAULT_PASSWORD", ""),
        "database_name": database_name,
    }
