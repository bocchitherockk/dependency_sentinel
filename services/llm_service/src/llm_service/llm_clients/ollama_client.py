from typing import Any, override
import json
from logging import Logger
import uuid

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
            'host': 'host.docker.internal',
            'port': 11434,
            'endpoint': 'http://host.docker.internal:11434',
            'supports_thinking': False,
            'supports_tool_calls': True,
        },
        'qwen3:8b': {
            'model_name': 'qwen3:8b',
            'host': 'host.docker.internal',
            'port': 11434,
            'endpoint': 'http://host.docker.internal:11434',
            'supports_thinking': True,
            'supports_tool_calls': True,
        },
    }

    def __init__(self, model_name: str):
        if model_name not in self.models.keys():
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
        if response_format is not None:
            body['format'] = response_format

        logger.info(f'LLM chat request sent to {self.model_name}')
        logger.debug(f'LLM chat request body: {json.dumps(body, indent=2)}')
        async with httpx.AsyncClient(timeout=None) as client:
            response = await client.post(
                f'{self.models[self.model_name]["endpoint"]}/api/chat',
                json=body,
            )
        response.raise_for_status()
        data = response.json()
        logger.info(f'LLM chat response received from {self.model_name}')
        logger.debug(f'LLM chat response: {json.dumps(data, indent=2)}')
        
        if response_format is None:
            return data['message']['content']
        else:
            return json.loads(data['message']['content'])

    @override
    async def agent(
        self,
        messages: list[dict[str, Any]],
        response_format: None | dict[str, Any] = None,
        temperature: float = 0.0,
        think: bool = False,
        mcp_client: fastmcp.Client | None = None,
    ):
        agent_loop_id: str = uuid.uuid4() # this is just fo logging purposes, however it could be later used to be stored in a database (it has to be better than this tho, maybe a uuid7)
        loop_count: int = 0 # this is just for logging purposes

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
            logger.info(f'(agent_loop={agent_loop_id}, model={self.model_name}), Prepared with tools: {len(tools)}')
            logger.debug(f'(agent_loop={agent_loop_id}, model={self.model_name}), Tools details: {json.dumps(tools, indent=2)}')

        while True:
            loop_count += 1
            logger.info(f'(agent_loop={agent_loop_id}, loop_count={loop_count}, model={self.model_name}), Request sent')
            logger.debug(f'(agent_loop={agent_loop_id}, loop_count={loop_count}, model={self.model_name}), Request body: {json.dumps(body, indent=2)}')
            async with httpx.AsyncClient(timeout=None) as client:
                response = await client.post(
                    f'{self.models[self.model_name]['endpoint']}/api/chat',
                    json=body,
                )
            response.raise_for_status()
            data = response.json()
            logger.info(f'(agent_loop={agent_loop_id}, loop_count={loop_count}, model={self.model_name}), Response received')
            logger.debug(f'(agent_loop={agent_loop_id}, loop_count={loop_count}, model={self.model_name}), Response: {json.dumps(data, indent=2)}')

            message = data['message']
            tool_calls = message.get('tool_calls', None)

            if not tool_calls:
                logger.info(f"(agent_loop={agent_loop_id}, loop_count={loop_count}, model={self.model_name}), LLM did not request any tool calls")
                break
            
            logger.info(f'(agent_loop={agent_loop_id}, loop_count={loop_count}, model={self.model_name}), Requested tool calls count: {len(tool_calls)}')
            logger.debug(f'(agent_loop={agent_loop_id}, loop_count={loop_count}, model={self.model_name}), Requested tool calls: {json.dumps(tool_calls, indent=2)}')

            messages.append(message)
            for tool_call in tool_calls:
                tool_name = tool_call['function']['name']
                tool_args = tool_call['function']['arguments']

                logger.info(f"(agent_loop={agent_loop_id}, loop_count={loop_count}, model={self.model_name}), Called tool: '{tool_name}'")
                logger.debug(f"(agent_loop={agent_loop_id}, loop_count={loop_count}, model={self.model_name}), Tool args: {tool_name} ({tool_args})")
                tool_result: CallToolResult = await mcp_client.call_tool(tool_name, tool_args)
                logger.info(f"(agent_loop={agent_loop_id}, loop_count={loop_count}, model={self.model_name}), Tool returned: '{tool_name}'")
                logger.debug(f"(agent_loop={agent_loop_id}, loop_count={loop_count}, model={self.model_name}), Tool result: {tool_name} -> {tool_result.content[0].text}")

                messages.append({
                    'role': 'tool',
                    'name': tool_name,
                    'content': tool_result.content[0].text,
                })

        if response_format is None:
            logger.info(f'(agent_loop={agent_loop_id}, model={self.model_name}), Response ready, no need to restructure')
            logger.debug(f'(agent_loop={agent_loop_id}, model={self.model_name}), Response: {message["content"]}')
            return message['content']
        else:
            body['format'] = response_format
            messages.append(message)
            messages.append({
                'role': 'user',
                'content': 'Respond in a strctured format'
            })

            logger.info(f'(agent_loop={agent_loop_id}, model={self.model_name}), Restructure request sent')
            logger.debug(f'(agent_loop={agent_loop_id}, model={self.model_name}), Restructure request body: {json.dumps(body, indent=2)}')
            async with httpx.AsyncClient(timeout=None) as client:
                response = await client.post(
                    f'{self.models[self.model_name]['endpoint']}/api/chat',
                    json=body,
                )
            response.raise_for_status()
            data = response.json()
            message = data['message']
            result = json.loads(message['content'])
            logger.info(f'(agent_loop={agent_loop_id}, model={self.model_name}), Restructure response received')
            logger.debug(f'(agent_loop={agent_loop_id}, model={self.model_name}), Restructure response: {json.dumps(data, indent=2)}')

            logger.info(f'(agent_loop={agent_loop_id}, model={self.model_name}), Response ready, restructured')
            logger.debug(f'(agent_loop={agent_loop_id}, model={self.model_name}), Restructured response: {json.dumps(result, indent=2)}')

            return result

logger.info(f'OllamaClient initialized with models: {list(OllamaClient.models.keys())}')
logger.debug(f'OllamaClient model details: {OllamaClient.models}')
