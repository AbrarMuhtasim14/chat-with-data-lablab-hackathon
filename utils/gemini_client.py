# utils/gemini_client.py
"""
Gemini API Client with Function Calling support.
Wrapper for Google's generativeai library.
"""

import json
import google.generativeai as genai
from typing import List, Dict, Any, Optional
from utils.config import GEMINI_API_KEY, GEMINI_MODEL

# Configure Gemini
genai.configure(api_key=GEMINI_API_KEY)


def convert_openai_tools_to_gemini(openai_schemas: List[Dict]) -> List[genai.protos.FunctionDeclaration]:
    """
    Convert OpenAI-style function schemas to Gemini FunctionDeclaration format.
    
    Args:
        openai_schemas: List of OpenAI tool schemas
        
    Returns:
        List of Gemini FunctionDeclaration objects
    """
    gemini_tools = []
    
    for schema in openai_schemas:
        if schema.get('type') != 'function':
            continue
            
        func = schema['function']
        
        # Convert properties
        properties = {}
        for prop_name, prop_def in func['parameters']['properties'].items():
            prop_type = _get_gemini_type(prop_def.get('type', 'string'))
            
            prop_schema = genai.protos.Schema(
                type=prop_type,
                description=prop_def.get('description', '')
            )
            
            # Handle arrays
            if prop_def.get('type') == 'array' and 'items' in prop_def:
                prop_schema.items = genai.protos.Schema(
                    type=_get_gemini_type(prop_def['items'].get('type', 'string'))
                )
            
            # Handle objects
            if prop_def.get('type') == 'object' and 'properties' in prop_def:
                nested_props = {}
                for nested_name, nested_def in prop_def['properties'].items():
                    nested_props[nested_name] = genai.protos.Schema(
                        type=_get_gemini_type(nested_def.get('type', 'string')),
                        description=nested_def.get('description', '')
                    )
                prop_schema.properties = nested_props
            
            properties[prop_name] = prop_schema
        
        # Create function declaration
        gemini_func = genai.protos.FunctionDeclaration(
            name=func['name'],
            description=func['description'],
            parameters=genai.protos.Schema(
                type=genai.protos.Type.OBJECT,
                properties=properties,
                required=func['parameters'].get('required', [])
            )
        )
        
        gemini_tools.append(gemini_func)
    
    return gemini_tools


def _get_gemini_type(openai_type: str) -> genai.protos.Type:
    """Map OpenAI type strings to Gemini Type enums."""
    type_map = {
        'string': genai.protos.Type.STRING,
        'object': genai.protos.Type.OBJECT,
        'array': genai.protos.Type.ARRAY,
        'number': genai.protos.Type.NUMBER,
        'integer': genai.protos.Type.INTEGER,
        'boolean': genai.protos.Type.BOOLEAN
    }
    return type_map.get(openai_type, genai.protos.Type.STRING)


class GeminiAgent:
    """Gemini-based conversational agent with function calling."""
    
    def __init__(self, system_instruction: str, tools: List[Dict]):
        """
        Initialize Gemini agent.
        
        Args:
            system_instruction: System prompt
            tools: List of OpenAI-style tool schemas
        """
        self.system_instruction = system_instruction
        self.gemini_tools = convert_openai_tools_to_gemini(tools)
        
        self.model = genai.GenerativeModel(
            model_name=GEMINI_MODEL,
            tools=self.gemini_tools,
            system_instruction=system_instruction
        )
        
        self.chat = None
    
    def start_chat(self):
        """Initialize a new chat session."""
        self.chat = self.model.start_chat(history=[])
        return self.chat
    
    def send_message(self, message: str) -> Any:
        """Send a message and get response."""
        if self.chat is None:
            self.start_chat()
        return self.chat.send_message(message)
    
    def send_function_response(self, function_name: str, result: Any) -> Any:
        """Send function execution result back to model."""
        response_content = genai.protos.Content(
            parts=[genai.protos.Part(
                function_response=genai.protos.FunctionResponse(
                    name=function_name,
                    response={'result': str(result)}
                )
            )]
        )
        return self.chat.send_message(response_content)