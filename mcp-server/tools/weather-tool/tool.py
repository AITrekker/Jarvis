"""
MCP Weather Server Tool

This is a Model Context Protocol (MCP) compliant tool that provides weather forecasts.
The server:
1. Advertises its capabilities through a tool description format
2. Implements the 'get-forecast' tool for retrieving weather data
3. Follows the MCP specification for stdin/stdout communication
4. Properly handles errors and returns them in the expected format

This demonstrates the basic structure of an MCP tool that can be called by any
MCP-compatible client, whether it's a CLI tool, API server, or language model.

Usage:
    # Run directly (for testing)
    python server.py
    
    # Then input JSON in MCP format, e.g.:
    {"type":"tool-call","tool":"get-forecast","input":{"location":"Seattle"}}
    
    # Typically this server is called by an MCP client rather than directly
    
    # In this Docker demo, the bridge service calls this tool via subprocess

Architecture in MCP-Demo:
    Browser → Frontend Container → Bridge Container → MCP Tool (this file)
    
    The bridge service (bridge.py) executes this script as a subprocess and
    communicates via stdin/stdout using the MCP protocol format.

Reference:
    For more information about the Model Context Protocol, see:
    https://modelcontextprotocol.io/
    
    APIs used:
    - Weather API: https://wttr.in/ (no API key needed, may have rate limits)
    
Note:
    This tool falls back to mock weather data if the external API is unavailable
    or rate-limited. For production use, consider using a more reliable weather
    service with proper API authentication and error handling.
"""
#!/usr/bin/env python3
import sys
import json
import requests
from random import choice

def load_schema():
    """
    Load schema.json so we can advertise on startup.
    """
    schema_path = __file__.replace("tool.py", "schema.json")
    raw = open(schema_path, "r").read()
    return json.loads(raw)

def describe_tools():
    """
    Print the MCP tool-description on stdout (once).
    """
    schema = load_schema()
    print(json.dumps({
        "type": "tool-description",
        "tools": [
            {
                "name": schema["name"],
                "description": schema["description"],
                "input_schema": schema["input_schema"],
                "output_schema": schema["output_schema"],
                "version": schema.get("version", "1.0.0")
            }
        ]
    }), flush=True)

def fetch_weather(location: str):
    """
    Attempt a real HTTP call to wttr.in (JSON format). If that fails,
    fall back to a random mock.
    """
    
    try:
        # Try to get data from a free weather API that doesn't require authentication
        url = f"https://wttr.in/{location}?format=j1"
        response = requests.get(url, timeout=3)
        
        if response.status_code == 200:
            data = response.json()
            temp = data.get("current_condition", [{}])[0].get("temp_F", "??")
            desc = data.get("current_condition", [{}])[0].get("weatherDesc", [{}])[0].get("value", "unknown")
            return {
                "location": location,
                "forecast": f"{desc} and {temp}°F in {location}"
            }
    except Exception as e:
        # Fallback mock response
        # Add error logging to stderr for debugging
        print(f"Weather API failed: {e}", file=sys.stderr)
        conditions = choice(["Sunny", "Cloudy", "Rainy", "Partly cloudy", "Clear skies"])
        temp = choice(range(60, 90))
        return {
            "location": location,
            "forecast": f"{conditions} and {temp}°F in {location}"
        }

def handle_call(tool_name: str, payload: dict):
    """
    When MCP server sends:
      { "type":"tool-call", "tool":"get-forecast", "input":{"location":"Seattle"} }
    """
    if tool_name == "get-forecast":
        loc = payload.get("location", "").strip()
        if not loc:
            return { "error": "Missing required field: location" }
        return fetch_weather(loc)
    else:
        return { "error": f"Unknown tool '{tool_name}'" }

def main():
    # 1) Print tool-description on stdout
    describe_tools()

    # 2) Wait for tool-call messages on stdin
    while True:
        raw = sys.stdin.readline()
        if raw == "":
            break
        try:
            msg = json.loads(raw.strip())
            if msg.get("type") == "tool-call":
                name = msg.get("tool", "")
                inp = msg.get("input", {})
                out = handle_call(name, inp)
                print(json.dumps({
                    "type": "tool-result",
                    "output": out
                }), flush=True)
            else:
                print(json.dumps({
                    "type": "error",
                    "error": "Expected 'tool-call'"
                }), flush=True)
        except Exception as e:
            print(json.dumps({
                "type": "error",
                "error": str(e)
            }), flush=True)

if __name__ == "__main__":
    main()
