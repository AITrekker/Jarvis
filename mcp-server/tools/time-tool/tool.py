"""
MCP Time Server Tool

This is a Model Context Protocol (MCP) compliant tool that provides current time information.
The server:
1. Advertises its capabilities through a tool description format
2. Implements the 'get-time' tool for retrieving time data for any location
3. Follows the MCP specification for stdin/stdout communication
4. Properly handles errors and returns them in the expected format

This demonstrates the basic structure of an MCP tool that can be called by any
MCP-compatible client, whether it's a CLI tool, API server, or language model.

Usage:
    # Run directly (for testing)
    python server.py
    
    # Then input JSON in MCP format, e.g.:
    {"type":"tool-call","tool":"get-time","input":{"location":"New York"}}
    
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
    - Geocoding: https://nominatim.openstreetmap.org/ (no API key needed)
    - Time API: https://timeapi.io/ (may have rate limits, falls back to UTC)
    
Note:
    This tool falls back to UTC time if the external APIs are unavailable
    or rate-limited. For production use, consider using a more reliable
    timezone service or implementing local timezone data.
"""

#!/usr/bin/env python3
import sys
import json
import datetime
import requests

# Nominatim requires a User-Agent header
HEADERS = {
    "User-Agent": "MCP-TimeServer/1.0"
}

def load_schema():
    """
    Loads schema.json so we can print the tool-description on startup.
    """
    schema_path = __file__.replace("tool.py", "schema.json")
    raw = open(schema_path, "r").read()
    return json.loads(raw)

def describe_tools():
    """
    On startup, MCP expects a JSON line of the form:
      { "type": "tool-description", "tools": [ { … } ] }
    We'll load our schema.json and wrap it accordingly.
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

def get_coordinates(location: str):
    """
    Use Nominatim (OpenStreetMap) to resolve location → (lat, lon).
    """
    try:
        url = "https://nominatim.openstreetmap.org/search"
        params = {"q": location, "format": "json"}
        headers = {"User-Agent": "MCP-TimeTool/1.0"}
        resp = requests.get(url, params=params, headers=headers, timeout=5)
        resp.raise_for_status()
        data = resp.json()
        if not data:
            return None
        lat = data[0]["lat"]
        lon = data[0]["lon"]
        return lat, lon
    except Exception:
        return None

def get_time_by_coordinates(lat, lon, location_name):
    """
    Call TimeAPI.io's /Time/current/coordinate endpoint to get time info.
    This API is free and doesn't require an API key.
    """
    try:
        url = "https://timeapi.io/api/Time/current/coordinate"
        params = {
            "latitude": lat,
            "longitude": lon
        }
        resp = requests.get(url, params=params, timeout=5)
        resp.raise_for_status()
        data = resp.json()
        
        current_dt = data.get("dateTime")
        tz_id = data.get("timeZone")
        
        if not current_dt or not tz_id:
            raise ValueError("Invalid response from time API")
            
        # Fix: Handle microseconds properly in datetime parsing
        try:
            # First try to parse as-is
            if current_dt.endswith('Z'):
                dt = datetime.datetime.fromisoformat(current_dt.replace('Z', '+00:00'))
            else:
                # Handle microseconds by truncating to 6 digits max
                if '.' in current_dt:
                    base, microseconds = current_dt.split('.')
                    # Truncate microseconds to 6 digits
                    microseconds = microseconds[:6].ljust(6, '0')
                    current_dt = f"{base}.{microseconds}"
                dt = datetime.datetime.fromisoformat(current_dt)
        except ValueError as parse_error:
            # If parsing fails, try a more robust approach
            import re
            # Remove microseconds entirely if they're causing issues
            clean_dt = re.sub(r'\.\d+', '', current_dt.replace('Z', ''))
            dt = datetime.datetime.fromisoformat(clean_dt)
        
        return {
            "location": location_name,
            "time": dt.strftime("%H:%M:%S"),
            "date": dt.strftime("%Y-%m-%d"),
            "timezone": tz_id
        }
        
    except Exception as e:
        # If the time API fails, return UTC time with error note
        utc_now = datetime.datetime.utcnow()
        return {
            "location": location_name,
            "time": utc_now.strftime("%H:%M:%S") + " (UTC)",
            "date": utc_now.strftime("%Y-%m-%d"),
            "timezone": f"Error: {str(e)} - showing UTC time",
        }

def handle_call(tool_name: str, payload: dict):
    """
    Called when the MCP server sends:
      { "type": "tool-call", "tool": "get-time", "input": { "location": "Seattle" } }
    """
    if tool_name == "get-time":
        loc = payload.get("location", "").strip()
        if not loc:
            return { "error": "Missing required field: location" }
        coords = get_coordinates(loc)
        if coords is None:
            return { "error": f"Could not geocode '{loc}'" }
        lat, lon = coords
        return get_time_by_coordinates(lat, lon, loc)
    else:
        return { "error": f"Unknown tool '{tool_name}'" }

def main():
    # 1) Advertise our schema.json on stdout:
    describe_tools()

    # 2) Wait for lines on stdin (MCP server will send us tool-call messages)
    while True:
        raw = sys.stdin.readline()
        if raw == "":
            break
        try:
            msg = json.loads(raw.strip())
            if msg.get("type") == "tool-call":
                tname = msg.get("tool", "")
                inp = msg.get("input", {})
                result = handle_call(tname, inp)
                print(json.dumps({
                    "type": "tool-result",
                    "output": result
                }), flush=True)
            else:
                # If we get anything other than a tool-call, return an error:
                print(json.dumps({
                    "type": "error",
                    "error": "Expected 'tool-call' message"
                }), flush=True)
        except Exception as e:
            print(json.dumps({
                "type": "error",
                "error": str(e)
            }), flush=True)

if __name__ == "__main__":
    main()
