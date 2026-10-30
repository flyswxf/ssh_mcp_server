# SSH MCP Server

让 AI Agent（Trae、VSCode、Cursor 等）通过 SSH 操作远端 CentOS 7 工作区。

## 设计理念

采用 Pi Agent 风格的极简设计，只提供 **3 个元操作**，最大化可组合性：

| 工具          | 说明                  |
| ----------- | ------------------- |
| `ssh_bash`  | 执行远端 shell 命令（万能工具） |
| `ssh_read`  | 读取远端文件内容（支持行范围）     |
| `ssh_write` | 写入远端文件（自动创建目录）      |

其他操作都可以通过组合实现：
- 列目录 → `ssh_bash("ls -la /path")`
- 搜索文件 → `ssh_bash("grep -rn pattern /path")`
- 复制文件 → `ssh_bash("cp src dst")`
- 移动文件 → `ssh_bash("mv src dst")`
- 删除文件 → `ssh_bash("rm file")`

## 安装

```bash
cd ssh_mcp_server
pip install -r requirements.txt
```

## 配置 SSH 连接

### 1. 生成 SSH 密钥（如果没有）

```bash
ssh-keygen -t rsa -b 4096
```

### 2. 将公钥复制到远端

```bash
ssh-copy-id root@100.95.144.153
```

或手动复制 `~/.ssh/id_rsa.pub` 到远端 `~/.ssh/authorized_keys`。

### 3. 测试连接

```bash
ssh root@100.95.144.153
```

## 在 IDE 中配置

### Trae / Cursor / VSCode

在项目根目录创建 `.trae/mcp.json`（或 `.vscode/mcp.json`）：

```json
{
  "mcpServers": {
    "ssh": {
      "command": "D:\\Apps\\Tools\\miniForge\\python.exe",
      "args": ["D:/code/Obsidian-main/ssh_mcp_server/server.py"],
      "env": {
        "SSH_HOST": "100.95.144.153",
        "SSH_USER": "root",
        "SSH_PORT": "22",
        "SSH_KEY_PATH": "C:/Users/w50064021/.ssh/id_rsa"
      }
    }
  }
}
```

### Claude Desktop

在 `claude_desktop_config.json` 中添加相同的配置。

## 使用示例

配置完成后，Agent 可以：

```python
# 执行命令
ssh_bash(command="ls -la /root")
ssh_bash(command="grep -rn 'def main' /project --include='*.py'")
ssh_bash(command="cd /project && python main.py")

# 读取文件
ssh_read(path="/root/main.py")
ssh_read(path="/var/log/syslog", offset=100, limit=50)

# 写入文件
ssh_write(path="/root/hello.py", content="print('hello world')")
ssh_write(path="/etc/myapp.conf", content="[section]\nkey=value")
```

## 工具详情

### ssh_bash

执行远端 shell 命令，最通用的工具。

**参数：**
- `command` (必填): Shell 命令
- `timeout` (可选): 超时秒数，默认 30，最大 300

**返回：**
```json
{
  "exit_code": 0,
  "stdout": "命令输出",
  "stderr": "错误信息"
}
```

**示例：**
```python
ssh_bash(command="ls -la /root")
ssh_bash(command="ps aux | grep python")
ssh_bash(command="docker ps")
ssh_bash(command="make build", timeout=120)
```

### ssh_read

读取远端文件内容，支持行范围。

**参数：**
- `path` (必填): 文件绝对路径
- `offset` (可选): 起始行号（0-based），默认从头
- `limit` (可选): 读取行数，默认 2000

**返回：**
带行号的文件内容（纯文本）

**示例：**
```python
ssh_read(path="/root/main.py")
ssh_read(path="/etc/nginx/nginx.conf", limit=100)
ssh_read(path="/var/log/syslog", offset=1000, limit=50)
```

### ssh_write

写入远端文件，自动创建父目录。

**参数：**
- `path` (必填): 文件绝对路径
- `content` (必填): 文件内容

**返回：**
操作结果信息

**示例：**
```python
ssh_write(path="/root/hello.py", content="print('hello')")
ssh_write(path="/project/config.yaml", content="key: value\nlist:\n  - item1\n  - item2")
```

## 故障排查

### SSH 连接失败

```
Permission denied for user root
```

**解决：**
1. 检查 SSH 密钥是否已复制到远端
2. 测试手动连接：`ssh root@100.95.144.153`
3. 检查 `SSH_KEY_PATH` 环境变量是否正确

### 命令超时

长时间运行的命令请设置 `timeout` 参数：

```python
ssh_bash(command="make build", timeout=120)
```

### 文件写入失败

检查：
- 远端目录权限
- 磁盘空间：`ssh_bash(command="df -h")`

## 架构

```
┌─────────────────┐     MCP      ┌──────────────┐     SSH      ┌─────────────┐
│  Trae/VSCode    │ ───────────→ │  SSH MCP     │ ───────────→ │  CentOS 7   │
│  Agent          │   (stdio)    │  Server      │   (async)    │  集群       │
└─────────────────┘              └──────────────┘              └─────────────┘
```

## 测试

```bash
cd D:\code\Obsidian-main\ssh_mcp_server
D:\Apps\Tools\miniForge\python.exe test_server.py
```

## License

MIT
