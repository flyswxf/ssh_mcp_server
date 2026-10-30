"""
SSH MCP Server 测试脚本

用于验证 SSH 连接和工具功能是否正常工作。
"""

import asyncio
import sys
from pathlib import Path

# 添加当前目录到路径
sys.path.insert(0, str(Path(__file__).parent))

from server import ssh_conn, bash_tool, read_tool, write_tool, BashInput, ReadInput, WriteInput


async def test_connection():
    """测试 SSH 连接"""
    print("=" * 60)
    print("测试 1: SSH 连接")
    print("=" * 60)
    
    try:
        await ssh_conn.connect()
        print("✓ SSH 连接成功")
        return True
    except Exception as e:
        print(f"✗ SSH 连接失败: {e}")
        return False


async def test_bash():
    """测试命令执行"""
    print("\n" + "=" * 60)
    print("测试 2: 执行命令 (ssh_bash)")
    print("=" * 60)
    
    params = BashInput(command="whoami && hostname && pwd")
    result = await bash_tool(params)
    print(result)
    
    if '"exit_code": 0' in result:
        print("✓ 命令执行成功")
        return True
    else:
        print("✗ 命令执行失败")
        return False


async def test_read():
    """测试文件读取"""
    print("\n" + "=" * 60)
    print("测试 3: 读取文件 (ssh_read)")
    print("=" * 60)
    
    params = ReadInput(path="/etc/hostname")
    result = await read_tool(params)
    print(result)
    
    if not result.startswith("Error"):
        print("✓ 文件读取成功")
        return True
    else:
        print("✗ 文件读取失败")
        return False


async def test_write():
    """测试文件写入"""
    print("\n" + "=" * 60)
    print("测试 4: 写入文件 (ssh_write)")
    print("=" * 60)
    
    test_file = "/tmp/ssh_mcp_test.txt"
    params = WriteInput(path=test_file, content="Hello from SSH MCP Server\nTest write operation")
    result = await write_tool(params)
    print(result)
    
    if result.startswith("✓"):
        print("✓ 文件写入成功")
        
        # 验证写入
        print("\n验证写入内容:")
        read_params = ReadInput(path=test_file)
        read_result = await read_tool(read_params)
        print(read_result)
        
        # 清理测试文件
        print("\n清理测试文件:")
        cleanup_params = BashInput(command=f"rm {test_file}")
        cleanup_result = await bash_tool(cleanup_params)
        print(cleanup_result)
        
        return True
    else:
        print("✗ 文件写入失败")
        return False


async def main():
    """运行所有测试"""
    print("\n" + "=" * 60)
    print("SSH MCP Server 测试")
    print("=" * 60)
    
    results = []
    
    # 测试连接
    if not await test_connection():
        print("\n✗ SSH 连接失败，请检查配置")
        return
    
    # 测试功能
    results.append(await test_bash())
    results.append(await test_read())
    results.append(await test_write())
    
    # 关闭连接
    await ssh_conn.close()
    
    # 总结
    print("\n" + "=" * 60)
    print("测试总结")
    print("=" * 60)
    passed = sum(results)
    total = len(results)
    print(f"通过: {passed}/{total}")
    
    if passed == total:
        print("\n✓ 所有测试通过！SSH MCP Server 可以正常工作。")
    else:
        print(f"\n✗ {total - passed} 个测试失败，请检查配置。")


if __name__ == "__main__":
    asyncio.run(main())
