import os
import json
from logging import Logger
from typing import Any, override
import uuid

from dotenv import load_dotenv
from groq import AsyncGroq
from groq.types.chat.chat_completion import ChatCompletion, ChatCompletionMessage
from groq.types.chat.chat_completion_message import ChatCompletionMessage
from groq.types.chat.chat_completion_message_tool_call import ChatCompletionMessageToolCall
import fastmcp
from fastmcp.client.client import CallToolResult
from mcp.types import Tool

from common.logging.global_logger import get_global_logger
from common.rate_limiter.RateLimiter import RateLimiter
from llm_service.llm_clients.llm_client import LLMClient


logger: Logger = get_global_logger(__name__)

load_dotenv()
logger.info('Environment variables loaded from .env file.')
logger.debug('Environment variables: ')
logger.debug(f'    GROQ_API_KEY: {os.getenv("GROQ_API_KEY")}')

logger.error('GroqClient is currently not working because it needs a robust rate limiter implementation.')

class GroqClient(LLMClient):
    models = {
        'openai/gpt-oss-120b': {
            'model_name': 'openai/gpt-oss-120b',
            'rate_limit_requests_per_minute': 30,
            'rate_limit_requests_per_day': 1_000,
            # TODO: check if the token limits are input or output or both, and adjust accordingly
            'rate_limit_tokens_per_minute': 8_000,
            'rate_limit_tokens_per_day': 200_000,
            'rate_limiter_requests_per_minute': RateLimiter(max_rate=30, time_window=60.0),
        }
    }

    def __init__(self, model_name):
        if model_name not in self.models.keys():
            logger.error(f"LLM model '{model_name}' is not supported.")
            raise ValueError(f"LLM model '{model_name}' is not supported.")

        self.model_name = model_name
        api_key = os.environ.get("GROQ_API_KEY")
        self.client: AsyncGroq = AsyncGroq(api_key=api_key)

    def convert_mcp_tools_to_expected_tools_format(self, tools: list[Tool]) -> list[dict[str, Any]]:
        result: list[dict[str, Any]] = []
        for tool in tools:
            result.append({
                'type': 'function',
                'function': {
                    'name': tool.name,
                    'description': tool.description,
                    'parameters': self.convert_json_schema_to_expected_json_schema_format(tool.inputSchema)[0],
                    'strict': True,
                },
            })
        return result

    def _convert_json_schema_to_expected_json_schema_format_recursive(self, node: Any):
        '''
        Recursively injects 'additionalProperties': False into every object block 
        found within a JSON schema dictionary.
        '''
        if isinstance(node, dict):
            for key, value in list(node.items()):
                node[key] = self._convert_json_schema_to_expected_json_schema_format_recursive(value)
                
            # If this dictionary represents a JSON Schema Object, add the key
            if node.get('type') == 'object':
                node['additionalProperties'] = False

        elif isinstance(node, list):
            # Handle elements inside arrays
            return [self._convert_json_schema_to_expected_json_schema_format_recursive(item) for item in node]

        return node

    def convert_json_schema_to_expected_json_schema_format(self, json_schema: dict[str, Any]) -> tuple[dict[str, Any], str | None]:
        # I have to do all of this because the Groq API does not accept a direct list as a JSON schema, it has to be wrapped in an object
        result: dict[str, Any] = self._convert_json_schema_to_expected_json_schema_format_recursive(json_schema)
        label: str | None = None

        if result.get('type') == 'array': # != 'object'
            result = {
                'type': 'object',
                'properties': {
                    'items': result
                },
                'required': ['items'],
                'additionalProperties': False,
            }
            label = 'items'

        return result, label

    @override
    async def chat(
        self,
        messages: list[dict[str, Any]],
        response_format: None | dict[str, Any] = None,
        temperature: float = 0.0,
        think: bool = False,
    ):
        corrected_response_format_label: None | str = None
        corrected_response_format: dict[str, Any] = { 'type': 'text' }
        if response_format is not None:
            schema, label = self.convert_json_schema_to_expected_json_schema_format(response_format)
            corrected_response_format_label = label
            corrected_response_format = {
                'type': 'json_schema',
                'json_schema': {
                    'name': 'dependency_sentinel', # this name has no effect on the output, but is required by the API, so i'll just use the name of the project
                    'strict': True,
                    'schema': schema,
                }
            }

        logger.info(f'LLM chat requested a rate limit acquisition for model: {self.model_name}')
        await self.models[self.model_name]['rate_limiter_requests_per_minute'].acquire(value=1)
        logger.info(f'LLM chat rate limit acquisition successful for model: {self.model_name}')

        logger.info(f'LLM chat request sent to {self.model_name}')
        chat_response: ChatCompletion = await self.client.chat.completions.create(
            model=self.model_name,
            messages=messages,
            temperature=temperature,
            response_format=corrected_response_format,
            reasoning_effort='medium',
        )
        logger.info(f'LLM chat response received from {self.model_name}')
        logger.debug(f'LLM chat response: {json.dumps(chat_response.model_dump(mode="json"), indent=2)}')

        if corrected_response_format['type'] == 'text':
            return chat_response.choices[0].message.content
        elif corrected_response_format['type'] == 'json_schema':
            result = json.loads(chat_response.choices[0].message.content)
            if corrected_response_format_label is not None:
                result = result.get(corrected_response_format_label)
            return result

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

        if mcp_client is not None:
            tools_list: list[Tool] = await mcp_client.list_tools()
            tools: list[dict[str, Any]] = self.convert_mcp_tools_to_expected_tools_format(tools_list)
            logger.info(f'(agent_loop={agent_loop_id}, model={self.model_name}), Prepared with tools: {len(tools)}')
            logger.debug(f'(agent_loop={agent_loop_id}, model={self.model_name}), Tools details: {json.dumps(tools, indent=2)}')

        request_config: dict[str, Any] = {
            'temperature': temperature,
            'reasoning_effort': 'medium', # i would have done `'medium' if think else 'none'` because 'none' is a possible value of reasoning_effort, however in reality the api accepts only these values : `low`, `medium`, or `high` otherwise it is a 400 bad request error, so i will just hardcode it to 'medium' for now
        }
        if mcp_client is not None:
            request_config['tools'] = tools

        while True:
            loop_count += 1

            logger.info(f'(agent_loop={agent_loop_id}, loop_count={loop_count}, model={self.model_name}), Requested a rate limit acquisition')
            await self.models[self.model_name]['rate_limiter_requests_per_minute'].acquire(value=1)
            logger.info(f'(agent_loop={agent_loop_id}, loop_count={loop_count}, model={self.model_name}), Rate limit acquisition successful')

            logger.info(f'(agent_loop={agent_loop_id}, loop_count={loop_count}, model={self.model_name}), Request sent')
            logger.debug(f'(agent_loop={agent_loop_id}, loop_count={loop_count}, model={self.model_name}), Request contents: {json.dumps(messages, indent=2)}')
            logger.debug(f'(agent_loop={agent_loop_id}, loop_count={loop_count}, model={self.model_name}), Request config: {json.dumps(request_config, indent=2)}')
            chat_response: ChatCompletion = await self.client.chat.completions.create(
                model=self.model_name,
                messages=messages,
                **request_config,
            )

            logger.info(f'(agent_loop={agent_loop_id}, loop_count={loop_count}, model={self.model_name}), Response received')
            logger.debug(f'(agent_loop={agent_loop_id}, loop_count={loop_count}, model={self.model_name}), Response: {chat_response.model_dump_json(indent=2)}')

            candidate: ChatCompletionMessage = chat_response.choices[0].message
            tool_calls: list[ChatCompletionMessageToolCall] = []
            if candidate.tool_calls is not None:
                tool_calls = candidate.tool_calls
            tool_calls_dict: list[dict[str, Any]] = [tool_call.model_dump(mode='json') for tool_call in tool_calls]

            if not tool_calls:
                logger.info(f"(agent_loop={agent_loop_id}, loop_count={loop_count}, model={self.model_name}), LLM did not request any tool calls")
                break

            logger.info(f'(agent_loop={agent_loop_id}, loop_count={loop_count}, model={self.model_name}), Requested tool calls count: {len(tool_calls)}')
            logger.debug(f'(agent_loop={agent_loop_id}, loop_count={loop_count}, model={self.model_name}), Requested tool calls: {json.dumps(tool_calls_dict, indent=2)}')

            messages.append({
                'role': 'assistant',
                'content': candidate.content,
                'tool_calls': tool_calls_dict,
            })
            for tool_call in tool_calls:
                tool_call_id: str = tool_call.id
                tool_name: str = tool_call.function.name
                tool_args: dict[str, Any] = json.loads(tool_call.function.arguments) # `tool_call.function.arguments` is a string, i will json.loads it without caring that it might not be a valid json and let the exception be raised

                logger.info(f"(agent_loop={agent_loop_id}, loop_count={loop_count}, model={self.model_name}), Called tool: '{tool_name}'")
                logger.debug(f"(agent_loop={agent_loop_id}, loop_count={loop_count}, model={self.model_name}), Tool args: {tool_name} ({tool_args})")
                tool_result: CallToolResult = await mcp_client.call_tool(tool_name, tool_args)
                logger.info(f"(agent_loop={agent_loop_id}, loop_count={loop_count}, model={self.model_name}), Tool returned: '{tool_name}'")
                logger.debug(f"(agent_loop={agent_loop_id}, loop_count={loop_count}, model={self.model_name}), Tool result: {tool_name} -> {tool_result.content[0].text}")

                messages.append({
                    'role': 'tool',
                    'tool_call_id': tool_call_id,
                    'content': tool_result.content[0].text,
                })

        if response_format is None:
            logger.info(f'(agent_loop={agent_loop_id}, model={self.model_name}), Response ready, no need to restructure')
            logger.debug(f'(agent_loop={agent_loop_id}, model={self.model_name}), Response: {candidate.content}')
            return candidate.content
        else:
            messages.append({
                'role': 'assistant',
                'content': candidate.content,
            })
            messages.append({
                'role': 'user',
                'content': 'Respond in a strctured format'
            })
        
            schema, label = self.convert_json_schema_to_expected_json_schema_format(response_format)
            corrected_response_format_label: str | None = label
            corrected_response_format: dict[str, Any] = {
                'type': 'json_schema',
                'json_schema': {
                    'name': 'dependency_sentinel', # this name has no effect on the output, but is required by the API, so i'll just use the name of the project
                    'strict': True,
                    'schema': schema,
                }
            }

            request_config = {
                'temperature': temperature,
                'reasoning_effort': 'medium',
                'response_format': corrected_response_format,
            }

            logger.info(f'(agent_loop={agent_loop_id}, model={self.model_name}), Restructure request sent')
            logger.debug(f'(agent_loop={agent_loop_id}, model={self.model_name}), Restructure request config: {json.dumps(request_config, indent=2)}')
            chat_response = await self.client.chat.completions.create(
                model=self.model_name,
                messages=messages,
                **request_config,
            )

            candidate = chat_response.choices[0].message
            result = json.loads(candidate.content)
            if corrected_response_format_label is not None:
                result = result.get(corrected_response_format_label)

            logger.info(f'(agent_loop={agent_loop_id}, model={self.model_name}), Restructure response received')
            logger.debug(f'(agent_loop={agent_loop_id}, model={self.model_name}), Restructure response: {json.dumps(chat_response.model_dump(mode="json"), indent=2)}')

            logger.info(f'(agent_loop={agent_loop_id}, model={self.model_name}), Response ready, restructured')
            logger.debug(f'(agent_loop={agent_loop_id}, model={self.model_name}), Restructured response: {json.dumps(result, indent=2)}')

            return result
