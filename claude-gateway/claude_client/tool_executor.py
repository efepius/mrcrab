import asyncio
import ipaddress
import os
import re
import socket
from urllib.parse import urlparse

import aiofiles
import aiohttp


# Commands that are never allowed regardless of context
BLOCKED_COMMANDS = [
    r"\brm\s+-rf\b",
    r"\bdd\b",
    r"\bmkfs\b",
    r"\bfdisk\b",
    r"\bformat\b",
    r"\bshred\b",
    r"\bwipefs\b",
    r">\s*/dev/",
    r"\bsudo\b",
    r"\bsu\s",
    r"\bchmod\s+777\b",
    r"\bpasswd\b",
    r"\.ssh",
    r"/etc/shadow",
    r"/etc/passwd",
    r"\biptables\b",
    r"\bufw\b",
    r"\bsystemctl\s+(stop|disable|mask)\b",
    r"\bkillall\b",
    r"\bpkill\b",
    r"\bcrontab\s+-r\b",
]

# RFC1918 private ranges — blocked for SSRF prevention
PRIVATE_RANGES = [
    ipaddress.ip_network("10.0.0.0/8"),
    ipaddress.ip_network("172.16.0.0/12"),
    ipaddress.ip_network("192.168.0.0/16"),
    ipaddress.ip_network("127.0.0.0/8"),
    ipaddress.ip_network("169.254.0.0/16"),
    ipaddress.ip_network("::1/128"),
    ipaddress.ip_network("fc00::/7"),
]


def _is_command_blocked(command: str) -> bool:
    for pattern in BLOCKED_COMMANDS:
        if re.search(pattern, command, re.IGNORECASE):
            return True
    return False


def _is_private_address(hostname: str) -> bool:
    try:
        addr = ipaddress.ip_address(socket.gethostbyname(hostname))
        return any(addr in net for net in PRIVATE_RANGES)
    except Exception:
        return False


def _safe_path(path: str, allowed_prefix: str) -> str | None:
    """Resolve and validate a path stays within allowed_prefix."""
    real = os.path.realpath(os.path.abspath(path))
    allowed = os.path.realpath(os.path.abspath(allowed_prefix))
    if real.startswith(allowed):
        return real
    return None


async def execute_bash(command: str, timeout: int, workspace_dir: str) -> str:
    if _is_command_blocked(command):
        return "ERROR: Command blocked by security policy."

    timeout = min(timeout, 60)

    try:
        os.makedirs(workspace_dir, exist_ok=True)
        proc = await asyncio.create_subprocess_shell(
            command,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.STDOUT,
            cwd=workspace_dir,
        )
        try:
            stdout, _ = await asyncio.wait_for(proc.communicate(), timeout=timeout)
            output = stdout.decode("utf-8", errors="replace").strip()
            return output[:8000] if len(output) > 8000 else output
        except asyncio.TimeoutError:
            proc.kill()
            return f"ERROR: Command timed out after {timeout}s"
    except Exception as e:
        return f"ERROR: {e}"


async def execute_read_file(path: str, data_dir: str) -> str:
    safe = _safe_path(path, data_dir)
    if not safe:
        return "ERROR: Access denied — path outside allowed directory."

    try:
        async with aiofiles.open(safe, "r", encoding="utf-8", errors="replace") as f:
            content = await f.read()
        if len(content) > 50000:
            content = content[:50000] + "\n[... truncated at 50000 chars ...]"
        return content
    except FileNotFoundError:
        return f"ERROR: File not found: {safe}"
    except Exception as e:
        return f"ERROR: {e}"


async def execute_write_file(path: str, content: str, data_dir: str) -> str:
    safe = _safe_path(path, data_dir)
    if not safe:
        return "ERROR: Access denied — path outside allowed directory."

    if len(content) > 10 * 1024 * 1024:
        return "ERROR: Content too large (max 10MB)."

    try:
        os.makedirs(os.path.dirname(safe), exist_ok=True)
        async with aiofiles.open(safe, "w", encoding="utf-8") as f:
            await f.write(content)
        return f"OK: Written {len(content)} chars to {safe}"
    except Exception as e:
        return f"ERROR: {e}"


async def execute_web_fetch(url: str, method: str = "GET", body: str | None = None) -> str:
    parsed = urlparse(url)
    if parsed.scheme not in ("http", "https"):
        return "ERROR: Only http/https URLs are supported."

    hostname = parsed.hostname or ""
    if _is_private_address(hostname):
        return "ERROR: Access to private/internal network addresses is blocked."

    try:
        async with aiohttp.ClientSession() as session:
            kwargs = {"timeout": aiohttp.ClientTimeout(total=15)}
            if method == "POST" and body:
                kwargs["data"] = body

            async with session.request(method, url, **kwargs) as resp:
                text = await resp.text()
                result = f"Status: {resp.status}\n\n{text}"
                return result[:10000] if len(result) > 10000 else result
    except aiohttp.ClientError as e:
        return f"ERROR: HTTP error — {e}"
    except Exception as e:
        return f"ERROR: {e}"


async def dispatch_tool(name: str, inputs: dict, workspace_dir: str, data_dir: str) -> str:
    if name == "bash":
        return await execute_bash(
            command=inputs.get("command", ""),
            timeout=inputs.get("timeout", 30),
            workspace_dir=workspace_dir,
        )
    elif name == "read_file":
        return await execute_read_file(path=inputs.get("path", ""), data_dir=data_dir)
    elif name == "write_file":
        return await execute_write_file(
            path=inputs.get("path", ""),
            content=inputs.get("content", ""),
            data_dir=data_dir,
        )
    elif name == "web_fetch":
        return await execute_web_fetch(
            url=inputs.get("url", ""),
            method=inputs.get("method", "GET"),
            body=inputs.get("body"),
        )
    else:
        return f"ERROR: Unknown tool '{name}'"
