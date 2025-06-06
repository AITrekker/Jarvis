"""
MCP Server

This Flask-based HTTP server acts as an intermediary between web browsers
and Model Context Protocol (MCP) tools. It provides a REST API interface that
translates HTTP requests into MCP protocol calls.

Architecture:
    Browser → HTTP Request → MCP Server → MCP Tool → HTTP Response → Browser
    
    The MCP server:
    1. Receives HTTP POST requests with JSON payloads
    2. Translates them into MCP protocol format
    3. Executes MCP tools as subprocesses via stdin/stdout
    4. Parses MCP tool responses and returns them as HTTP JSON responses
    5. Handles CORS to allow browser access from different origins

Endpoints:
    POST /weather - Get weather forecast for a location
    POST /time    - Get current time for a location

Usage in MCP_Docker-Demo:
    This service runs in a Docker container and is called by the frontend
    container's JavaScript code. It serves as the MCP server that hosts
    and executes MCP tools.

    Frontend (mcp_host.html) → MCP Server (this file) → MCP Tools (weather/time tools)

Docker Integration:
    - Runs on port 5000 inside the mcp-server container
    - Exposed to host machine via docker-compose port mapping
    - Contains weather-tool and time-tool Python scripts
    - Executes MCP tools as subprocesses within the same container

Protocol Translation:
    HTTP Request:  {"location": "Seattle"}
    MCP Format:    {"type": "tool-call", "tool": "get-forecast", "input": {"location": "Seattle"}}
    MCP Response:  {"type": "tool-result", "output": {"location": "Seattle", "forecast": "..."}}
    HTTP Response: {"location": "Seattle", "forecast": "..."}

Reference:
    For more information about the Model Context Protocol, see:
    https://modelcontextprotocol.io/
"""
import os
import json
import subprocess
from flask import Flask, request, jsonify
from flask_cors import CORS

app = Flask(__name__)
CORS(app)

# === 1) On startup, discover every subfolder under /app/tools that has schema.json + tool.py ===
# Get the directory where the current script is located
SCRIPT_DIR = os.path.dirname(os.path.realpath(__file__))
TOOLS_DIR = os.path.join(SCRIPT_DIR, "tools")
tool_registry = {}  # maps tool_name -> { "path": "path/to/tool.py", "schema": {…} }

def load_all_tools():
    """
    Walk /app/tools, find each folder that has schema.json + tool.py,
    read its "name" field, and register it in tool_registry.
    """
    if not os.path.isdir(TOOLS_DIR):
        print(f"Error: {TOOLS_DIR} does not exist or is not a directory.")
        return

    for item in os.listdir(TOOLS_DIR):
        candidate = os.path.join(TOOLS_DIR, item)
        schema_path = os.path.join(candidate, "schema.json")
        tool_py_path = os.path.join(candidate, "tool.py")

        if os.path.isdir(candidate) and os.path.isfile(schema_path) and os.path.isfile(tool_py_path):
            try:
                with open(schema_path, "r") as f:
                    schema = json.load(f)
                tool_name = schema.get("name")
                if tool_name:
                    tool_registry[tool_name] = {
                        "path": tool_py_path,
                        "schema": schema
                    }
            except json.JSONDecodeError:
                print(f"Warning: Could not parse JSON in {schema_path}")
    print("Discovered MCP tools:", list(tool_registry.keys()))

load_all_tools()

# === 2) Helper to invoke a tool's Python script as a subprocess ===
def call_mcp_tool(tool_path, tool_name, input_data):
    """
    Spawn: python <tool_path>
    Send on stdin: { "type":"tool-call", "tool":tool_name, "input": input_data }
    Capture stdout, find the first line of type "tool-result" or "error".
    """
    try:
        mcp_request = {
            "type": "tool-call",
            "tool": tool_name,
            "input": input_data
        }
        # Run the tool as a subprocess, send JSON on stdin
        result = subprocess.run(
            ["python", tool_path],
            input=json.dumps(mcp_request),
            capture_output=True,
            text=True,
            timeout=20
        )

        if result.returncode != 0:
            # If the script crashed, return its stderr as an error
            return { "error": f"Tool execution failed: {result.stderr.strip()}" }

        # The tool may have printed multiple lines (first is tool-description).
        # We search for the first JSON line with type "tool-result" or "error".
        for line in result.stdout.strip().split("\n"):
            try:
                parsed = json.loads(line)
                if parsed.get("type") == "tool-result":
                    return parsed.get("output", {})
                elif parsed.get("type") == "error":
                    return { "error": parsed.get("error", "Unknown error") }
            except json.JSONDecodeError:
                continue

        # If we never saw a valid result or error, return a fallback error:
        return { "error": "No valid tool-result found in tool stdout." }

    except Exception as e:
        return { "error": str(e) }

# === 3) Endpoint: GET /tools → lists all tools + their schemas ===
@app.route("/tools", methods=["GET"])
def list_tools():
    all_tools = []
    for info in tool_registry.values():
        s = info["schema"]
        all_tools.append({
            "name": s["name"],
            "description": s["description"],
            "input_schema": s["input_schema"],
            "output_schema": s["output_schema"],
            "version": s.get("version", "unknown")
        })
    return jsonify({ "tools": all_tools })

# === 4) Endpoint: POST /tool/<tool_name> → invoke that tool ===
@app.route("/tool/<tool_name>", methods=["POST"])
def invoke_tool(tool_name):
    # 4a) Does this tool exist?
    info = tool_registry.get(tool_name)
    if not info:
        return jsonify({ "error": f"No such tool: {tool_name}" }), 404

    # 4b) Validate required fields (simple check) against input_schema:
    schema = info["schema"].get("input_schema", {})
    payload = request.get_json() or {}
    missing = []
    for field in schema.get("required", []):
        if field not in payload:
            missing.append(field)
    if missing:
        return jsonify({ "error": f"Missing required field(s): {', '.join(missing)}" }), 400

    # 4c) Spawn the subprocess and return its output:
    tool_path = info["path"]
    result = call_mcp_tool(tool_path, tool_name, payload)
    return jsonify(result)

# === 5) Run the Flask app ===
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True) 