from typing import Any, override
import json

import httpx
import fastmcp
from fastmcp.client.client import CallToolResult
from mcp.types import Tool
from llm_service.llm_clients.llm_client import LLMClient

class OllamaClient(LLMClient):
    models = {
        'qwen2.5-coder:1.5b': {
            'model_name': 'qwen2.5-coder:1.5b',
            'host': '127.0.0.1',
            'port': 11434,
            'endpoint': 'http://127.0.0.1:11434',
            'supports_thinking': False,
            'supports_tool_calls': True,
        },
        'qwen3:8b': {
            'model_name': 'qwen3:8b',
            'host': '127.0.0.1',
            'port': 11434,
            'endpoint': 'http://127.0.0.1:11434',
            'supports_thinking': True,
            'supports_tool_calls': True,
        },
    }
    def __init__(self, model_name: str):
        if model_name not in self.models:
            raise ValueError(f"LLM model '{model_name}' is not supported.")
        self.model_name = model_name

    def convert_mcp_tools_to_expected_tools_format(self, tools: list[Tool]) -> list[dict[str, Any]]:
        result: list[dict[str, Any]] = []
        for tool in tools:
            result.append({
                'type': 'function',
                'function': {
                    'name': tool.name,
                    'description': tool.description,
                    'parameters': tool.inputSchema,
                },
            })
        return result

    @override
    async def chat(
        self,
        messages: list[dict[str, Any]],
        response_format: None | dict[str, Any] = None,
        temperature: float = 0.0,
        think: bool = False,
        mcp_client: fastmcp.Client = None,
    ):
        body = {
            'model': self.model_name,
            'stream': False,
            'messages': messages,
            'options': {
                'temperature': temperature,
            }
        }
        if OllamaClient.models[self.model_name]['supports_thinking']:
            body['think'] = think
        if mcp_client is not None:
            tools_list: list[Tool] = await mcp_client.list_tools()
            tools = self.convert_mcp_tools_to_expected_tools_format(tools_list)
            body['tools'] = tools

        while True:
            async with httpx.AsyncClient(timeout=None) as client:
                response = await client.post(
                    f'{self.models[self.model_name]['endpoint']}/api/chat',
                    json=body,
                )

            response.raise_for_status()
            data = response.json()
            message = data['message']
            tool_calls = message.get('tool_calls', None)

            if not tool_calls:
                break

            messages.append(message)
            for tool_call in tool_calls:
                tool_name = tool_call['function']['name']
                tool_args = tool_call['function']['arguments']

                tool_result: CallToolResult = await mcp_client.call_tool(tool_name, tool_args)

                messages.append({
                    'role': 'tool',
                    'name': tool_name,
                    'content': tool_result.content[0].text,
                })

        if response_format is None:
            return message['content']
        else:
            body['format'] = response_format
            messages.append(message)
            messages.append({
                'role': 'user',
                'content': 'Respond in a strctured format'
            })
            async with httpx.AsyncClient(timeout=None) as client:
                response = await client.post(
                    f'{self.models[self.model_name]['endpoint']}/api/chat',
                    json=body,
                )

            response.raise_for_status()
            data = response.json()
            message = data['message']
            content = message['content']
            return json.loads(content)
