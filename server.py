"""
SSH MCP Server - Pi Agent 风格极简版

只有 3 个元操作：
- bash: 执行任意 shell 命令
- read: 读取文件
- write: 写入文件

设计理念：最小化原语，最大化可组合性
"""

import asyncio
import json
import os
from pathlib import Path
from typing import Optional

import asyncssh
from mcp.server.fastmcp import FastMCP
from pydantic import BaseModel, Field, ConfigDict


# ============================================================================
# 配置
# ============================================================================

DEFAULT_HOST = os.getenv("SSH_HOST", "100.95.144.153")
DEFAULT_USER = os.getenv("SSH_USER", "root")
DEFAULT_PORT = int(os.getenv("SSH_PORT", "22"))
DEFAULT_KEY_PATH = os.getenv("SSH_KEY_PATH", str(Path.home() / ".ssh" / "id_rsa"))

CHARACTER_LIMIT = 50000  # 50KB 响应限制


# ============================================================================
# SSH 连接管理
# ============================================================================

class SSHConnection:
    """SSH 连接管理器"""
    
    def __init__(self):
        self._conn: Optional[asyncssh.SSHClientConnection] = None
        self._lock = asyncio.Lock()
    
    async def connect(self) -> None:
        """建立 SSH 连接"""
        async with self._lock:
            if self._conn and not self._conn.is_closing():
                return
            
            connect_kwargs = {
                "host": DEFAULT_HOST,
                "port": DEFAULT_PORT,
                "username": DEFAULT_USER,
                "known_hosts": None,
            }
            
            if DEFAULT_KEY_PATH and Path(DEFAULT_KEY_PATH).exists():
                connect_kwargs["client_keys"] = [DEFAULT_KEY_PATH]
            
            self._conn = await asyncssh.connect(**connect_kwargs)
    
    async def close(self) -> None:
        """关闭 SSH 连接"""
        if self._conn:
            self._conn.close()
            await self._conn.wait_closed()
            self._conn = None
    
    async def exec(self, command: str, timeout: int = 30) -> tuple[int, str, str]:
        """执行命令，返回 (exit_code, stdout, stderr)"""
        if not self._conn or self._conn.is_closing():
            await self.connect()
        
        try:
            result = await asyncio.wait_for(
                self._conn.run(command),
                timeout=timeout
            )
            return result.exit_status, result.stdout, result.stderr
        except asyncio.TimeoutError:
            return -1, "", f"Command timed out after {timeout}s"
        except Exception as e:
            return -1, "", str(e)


ssh_conn = SSHConnection()


# ============================================================================
# 输入模型
# ============================================================================

class BashInput(BaseModel):
    """执行 shell 命令的输入"""
    model_config = ConfigDict(str_strip_whitespace=True, extra='forbid')
    
    command: str = Field(
        ...,
        description="Shell 命令 (e.g., 'ls -la', 'grep -rn def', 'python script.py')",
        min_length=1,
        max_length=10000
    )
    timeout: Optional[int] = Field(
        default=30,
        description="超时秒数，默认 30，最大 300",
        ge=1,
        le=300
    )


class ReadInput(BaseModel):
    """读取文件的输入"""
    model_config = ConfigDict(str_strip_whitespace=True, extra='forbid')
    
    path: str = Field(
        ...,
        description="文件绝对路径 (e.g., '/root/main.py')",
        min_length=1,
        max_length=1000
    )
    offset: Optional[int] = Field(
        default=0,
        description="起始行号（0-based），默认从头开始",
        ge=0
    )
    limit: Optional[int] = Field(
        default=2000,
        description="读取行数，默认 2000 行",
        ge=1,
        le=10000
    )


class WriteInput(BaseModel):
    """写入文件的输入"""
    model_config = ConfigDict(str_strip_whitespace=False, extra='forbid')
    
    path: str = Field(
        ...,
        description="文件绝对路径",
        min_length=1,
        max_length=1000
    )
    content: str = Field(
        ...,
        description="文件内容",
        min_length=0,
        max_length=200000  # 200KB
    )


# ============================================================================
# MCP 工具
# ============================================================================

mcp = FastMCP("ssh_mcp")


@mcp.tool(
    name="ssh_bash",
    annotations={
        "title": "执行远端 shell 命令",
        "readOnlyHint": False,
        "destructiveHint": False,
        "idempotentHint": False,
        "openWorldHint": True
    }
)
async def bash_tool(params: BashInput) -> str:
    """在远端执行 shell 命令。
    
    这是最通用的工具，可以完成几乎所有操作：
    - 文件操作：ls, cat, cp, mv, rm, chmod, find
    - 文本处理：grep, sed, awk, head, tail, wc
    - 系统管理：ps, top, df, free, systemctl
    - 开发工具：python, pip, git, docker, make
    - 网络工具：curl, wget, ping, netstat, ss
    
    Args:
        command: Shell 命令
        timeout: 超时秒数（默认 30）
    
    Returns:
        JSON 格式：{"exit_code": int, "stdout": str, "stderr": str}
    
    Examples:
        bash(command="ls -la /root")
        bash(command="grep -rn 'def main' /project --include='*.py'")
        bash(command="cd /project && python main.py")
        bash(command="ps aux | grep python")
    """
    exit_code, stdout, stderr = await ssh_conn.exec(params.command, params.timeout)
    
    # 截断过长输出
    if len(stdout) > CHARACTER_LIMIT:
        stdout = stdout[:CHARACTER_LIMIT] + f"\n... (truncated, {len(stdout)} chars total)"
    if len(stderr) > CHARACTER_LIMIT // 2:
        stderr = stderr[:CHARACTER_LIMIT // 2] + f"\n... (truncated)"
    
    return json.dumps({
        "exit_code": exit_code,
        "stdout": stdout,
        "stderr": stderr
    }, ensure_ascii=False, indent=2)


@mcp.tool(
    name="ssh_read",
    annotations={
        "title": "读取远端文件",
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": True,
        "openWorldHint": True
    }
)
async def read_tool(params: ReadInput) -> str:
    """读取远端文件内容。
    
    比 bash cat 更结构化，支持行范围读取，适合查看代码和配置。
    
    Args:
        path: 文件绝对路径
        offset: 起始行号（0-based），默认从头
        limit: 读取行数，默认 2000
    
    Returns:
        文件内容（纯文本），带行号前缀
    
    Examples:
        read(path="/root/main.py")
        read(path="/var/log/syslog", offset=100, limit=50)
        read(path="/etc/nginx/nginx.conf", limit=100)
    """
    # 使用 sed 读取指定范围
    if params.offset > 0:
        cmd = f"sed -n '{params.offset + 1},{params.offset + params.limit}p' {params.path}"
    else:
        cmd = f"head -n {params.limit} {params.path}"
    
    exit_code, stdout, stderr = await ssh_conn.exec(cmd)
    
    if exit_code != 0:
        return f"Error: {stderr}"
    
    # 添加行号
    lines = stdout.split('\n')
    numbered = []
    for i, line in enumerate(lines, start=params.offset + 1):
        numbered.append(f"{i:6d}\t{line}")
    
    result = '\n'.join(numbered)
    
    if len(result) > CHARACTER_LIMIT:
        result = result[:CHARACTER_LIMIT] + "\n... (truncated)"
    
    return result


@mcp.tool(
    name="ssh_write",
    annotations={
        "title": "写入远端文件",
        "readOnlyHint": False,
        "destructiveHint": True,
        "idempotentHint": False,
        "openWorldHint": True
    }
)
async def write_tool(params: WriteInput) -> str:
    """写入内容到远端文件。
    
    完全覆盖原文件，自动创建父目录。
    
    Args:
        path: 文件绝对路径
        content: 文件内容
    
    Returns:
        操作结果
    
    Examples:
        write(path="/root/hello.py", content="print('hello')")
        write(path="/etc/myapp.conf", content="[section]\\nkey=value")
    """
    # 创建父目录
    parent = str(Path(params.path).parent)
    await ssh_conn.exec(f"mkdir -p {parent}")
    
    # 使用 heredoc 写入（避免转义问题）
    escaped = params.content.replace("'", "'\\''")
    cmd = f"cat > {params.path} << 'WRITE_EOF'\n{escaped}\nWRITE_EOF"
    
    exit_code, stdout, stderr = await ssh_conn.exec(cmd)
    
    if exit_code != 0:
        return f"Error: {stderr}"
    
    # 验证写入
    exit_code, stdout, _ = await ssh_conn.exec(f"wc -l {params.path}")
    lines = stdout.strip().split()[0] if exit_code == 0 else "?"
    
    return f"✓ Wrote {lines} lines to {params.path}"


# ============================================================================
# 启动
# ============================================================================

if __name__ == "__main__":
    mcp.run()
