import os
import json
import logging

class ToolManager:
    def __init__(self, tool_dir="mcp-server/tools"):
        self.tool_dir = tool_dir
        self.logger = logging.getLogger(__name__)
        self.tools = self._discover_tools()

    def _discover_tools(self):
        tool_registry = {}
        if not os.path.isdir(self.tool_dir):
            self.logger.warning(f"Tool directory not found: {self.tool_dir}")
            return tool_registry

        for tool_name in os.listdir(self.tool_dir):
            tool_path = os.path.join(self.tool_dir, tool_name)
            schema_path = os.path.join(tool_path, "schema.json")
            if os.path.isdir(tool_path) and os.path.exists(schema_path):
                with open(schema_path, 'r') as f:
                    schema = json.load(f)
                tool_registry[schema['name']] = schema
        self.logger.info(f"Discovered tools: {list(tool_registry.keys())}")
        return tool_registry

    def get_tools(self):
        return self.tools

    def get_tool_prompt(self, user_message):
        if not self.tools:
            return None

        # Base prompt structure from the excellent MCP-Demo
        prompt = "You are a tool router. Analyze the user's message and determine if it requires a specific tool.\n\n"
        
        # Dynamically add tool descriptions
        prompt += "Available tools:\n"
        for name, schema in self.tools.items():
            prompt += f"{name}: {schema['description']}\n"
            
        prompt += f'\nUser message: "{user_message}"\n\n'
        
        # Collect all possible input parameters from all tools
        all_params = set()
        for schema in self.tools.values():
            if "properties" in schema.get("input_schema", {}):
                for param in schema["input_schema"]["properties"].keys():
                    all_params.add(param)

        # Add response format instructions
        prompt += "Respond with ONLY a JSON object in this exact format:\n"
        prompt += '{\n'
        prompt += '  "tool": "tool-name-here" or null,\n'
        for param in sorted(list(all_params)): # sorted for consistent order
            prompt += f'  "{param}": "extracted-{param}" or null,\n'
        prompt += '  "confidence": 0.0-1.0\n'
        prompt += '}\n\n'

        # Add dynamic rules
        prompt += "Rules:\n"
        for name, schema in self.tools.items():
            params_desc = []
            if "properties" in schema.get("input_schema", {}):
                params_desc = list(schema["input_schema"]["properties"].keys())
            
            if params_desc:
                prompt += f'- Use "{name}" for {schema["description"].lower()}. It requires these parameters: {", ".join(params_desc)}\n'
            else:
                prompt += f'- Use "{name}" for {schema["description"].lower()}.\n'

        prompt += "- Set tool to null for greetings, general questions, or any message without clear tool intent.\n"
        prompt += "- For the chosen tool, extract the required parameters from the user message.\n"
        prompt += "- If a tool is not chosen, or if a parameter is not present in the message, its value must be null.\n"
        prompt += "- Set confidence between 0.0 and 1.0 based on how certain you are.\n"
        prompt += "- Be conservative: when in doubt, set tool to null and confidence low.\n"
        prompt += "- Respond with ONLY the JSON object - no markdown, no code blocks, no extra text.\n\n"

        # Add dynamic examples
        prompt += "Examples:\n"
        prompt += '- "hi" → {"tool": null, "confidence": 0.1'
        for param in sorted(list(all_params)):
             prompt += f', "{param}": null'
        prompt += '}\n'

        for name, schema in self.tools.items():
            if name == "get-forecast":
                prompt += '- "what\'s the weather in Paris?" → {"tool": "get-forecast", "confidence": 0.9, "location": "Paris"'
                for param in sorted(list(all_params)):
                    if param != "location":
                        prompt += f', "{param}": null'
                prompt += '}\n'
            elif name == "get-time":
                prompt += '- "current time in Tokyo" → {"tool": "get-time", "confidence": 0.9, "location": "Tokyo"'
                for param in sorted(list(all_params)):
                    if param != "location":
                        prompt += f', "{param}": null'
                prompt += '}\n'
            elif name == "web-search":
                prompt += '- "latest news on AI" → {"tool": "web-search", "confidence": 0.9, "query": "latest news on AI"'
                for param in sorted(list(all_params)):
                    if param != "query":
                        prompt += f', "{param}": null'
                prompt += '}\n'

        prompt += '- "tell me about physics" → {"tool": null, "confidence": 0.1'
        for param in sorted(list(all_params)):
             prompt += f', "{param}": null'
        prompt += '}'

        self.logger.debug(f"Generated tool prompt:\n{prompt}")
        return prompt