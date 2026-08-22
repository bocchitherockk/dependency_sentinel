from typing import Any, override
import json
from logging import Logger

import httpx
import fastmcp
from fastmcp.client.client import CallToolResult
from mcp.types import Tool

from common.logging.global_logger import get_global_logger
from llm_service.llm_clients.llm_client import LLMClient

logger: Logger = get_global_logger(__name__)

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
            logger.error(f"LLM model '{model_name}' is not supported.")
            raise ValueError(f"LLM model '{model_name}' is not supported.")
        self.model_name = model_name
        logger.info(f'OllamaClient initialized with model: {self.model_name}')

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
            logger.info(f'LLM chat request prepared with {len(tools)} tools for model: {self.model_name}')
            logger.debug(f'Tools details: {json.dumps(tools, indent=2)}')

        while True:
            async with httpx.AsyncClient(timeout=None) as client:
                logger.info(f'LLM chat request sent to {self.model_name}')
                logger.debug(f'Request body: {json.dumps(body, indent=2)}')
                response = await client.post(
                    f'{self.models[self.model_name]['endpoint']}/api/chat',
                    json=body,
                )
                logger.info(f'LLM chat response received from {self.model_name}')

            response.raise_for_status()
            data = response.json()
            logger.debug(f'Response data: {json.dumps(data, indent=2)}')
            message = data['message']
            tool_calls = message.get('tool_calls', None)

            if not tool_calls:
                logger.info(f'LLM did not request any tool calls for model: {self.model_name}')
                break
            
            logger.info(f'LLM requested {len(tool_calls)} tool calls')
            logger.debug(f'Tool calls requested: {json.dumps(tool_calls, indent=2)}')

            messages.append(message)
            for tool_call in tool_calls:
                tool_name = tool_call['function']['name']
                tool_args = tool_call['function']['arguments']

                tool_result: CallToolResult = await mcp_client.call_tool(tool_name, tool_args)
                logger.info(f"Tool '{tool_name}' called with arguments: {tool_args}")
                logger.debug(f"Tool '{tool_name}' result: {tool_result.content[0].text}")

                messages.append({
                    'role': 'tool',
                    'name': tool_name,
                    'content': tool_result.content[0].text,
                })

        if response_format is None:
            logger.info(f'LLM chat response received from {self.model_name}')
            logger.debug(f'Response message: {json.dumps(message, indent=2)}')
            return message['content']
        else:
            body['format'] = response_format
            messages.append(message)
            messages.append({
                'role': 'user',
                'content': 'Respond in a strctured format'
            })
            async with httpx.AsyncClient(timeout=None) as client:
                logger.info(f'LLM restructure request sent to {self.model_name}')
                logger.debug(f'Request body: {json.dumps(body, indent=2)}')
                response = await client.post(
                    f'{self.models[self.model_name]['endpoint']}/api/chat',
                    json=body,
                )
                logger.info(f'LLM restructure response received from {self.model_name}')
                logger.debug(f'Response data: {json.dumps(data, indent=2)}')

            response.raise_for_status()
            data = response.json()
            message = data['message']
            content = message['content']
            logger.debug(f'json schema: {json.dumps(response_format, indent=2)}')
            logger.debug(f'Restructured response content: {content}')
            return json.loads(content)

logger.info(f'OllamaClient initialized with models: {list(OllamaClient.models.keys())}')
logger.debug(f'OllamaClient model details: {OllamaClient.models}')
