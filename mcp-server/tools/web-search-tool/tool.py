import sys
import json
from duckduckgo_search import DDGS

def load_schema():
    schema_path = __file__.replace("tool.py", "schema.json")
    with open(schema_path, "r") as f:
        return json.load(f)

def describe_tools():
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

def handle_call(tool_name, payload):
    if tool_name == "web-search":
        query = payload.get("query", "").strip()
        if not query:
            return {"error": "Missing required field: query"}
        
        try:
            with DDGS() as ddgs:
                search_results = [r['body'] for r in ddgs.text(query, max_results=5)]
            
            return {
                "query": query,
                "results": search_results
            }
        except Exception as e:
            return {"error": f"An error occurred during web search: {e}"}
    else:
        return {"error": f"Unknown tool '{tool_name}'"}

def main():
    describe_tools()
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