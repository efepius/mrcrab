# OpenAI-compatible tool definitions (works with NVIDIA NIM, Kimi, Groq, Ollama, etc.)

def _tool(name: str, description: str, properties: dict, required: list) -> dict:
    return {
        "type": "function",
        "function": {
            "name": name,
            "description": description,
            "parameters": {
                "type": "object",
                "properties": properties,
                "required": required,
            },
        },
    }


OPENAI_TOOL_DEFINITIONS = [
    _tool(
        name="bash",
        description=(
            "Execute a shell command on the Ubuntu server. "
            "Use for system tasks, running scripts, checking processes, etc. "
            "Commands run in a sandboxed workspace directory. Output is returned as text."
        ),
        properties={
            "command": {"type": "string", "description": "The bash command to execute"},
            "timeout": {"type": "integer", "description": "Timeout in seconds (max 60)", "default": 30},
        },
        required=["command"],
    ),
    _tool(
        name="read_file",
        description=(
            "Read the contents of a file on the server. "
            "Only files within the allowed data directory can be read."
        ),
        properties={
            "path": {"type": "string", "description": "Absolute file path to read"},
        },
        required=["path"],
    ),
    _tool(
        name="write_file",
        description=(
            "Write content to a file on the server. "
            "Only files within the allowed data directory can be written."
        ),
        properties={
            "path": {"type": "string", "description": "Absolute file path to write"},
            "content": {"type": "string", "description": "Content to write to the file"},
        },
        required=["path", "content"],
    ),
    _tool(
        name="web_fetch",
        description=(
            "Fetch content from a URL. Returns the response body as text. "
            "Cannot access private/internal network addresses."
        ),
        properties={
            "url": {"type": "string", "description": "The URL to fetch"},
            "method": {"type": "string", "enum": ["GET", "POST"], "default": "GET", "description": "HTTP method"},
            "body": {"type": "string", "description": "Request body for POST requests"},
        },
        required=["url"],
    ),
]
