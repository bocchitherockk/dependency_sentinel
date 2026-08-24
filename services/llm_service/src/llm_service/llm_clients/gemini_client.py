import json
import os
from typing import Any, override
from logging import Logger
import uuid

from dotenv import load_dotenv
import fastmcp
from fastmcp.client.client import CallToolResult
from google.genai import Client
from google.genai import types

from common.logging.global_logger import get_global_logger
from llm_service.llm_clients.llm_client import LLMClient

logger: Logger = get_global_logger(__name__)

load_dotenv()
logger.info('Environment variables loaded from .env file.')
logger.debug('Environment variables: ')
logger.debug(f'    GEMINI_API_KEY: {os.getenv("GEMINI_API_KEY")}')


class GeminiClient(LLMClient):
    def __init__(self, model_name: str):
        self.model_name = model_name
        api_key = os.getenv('GEMINI_API_KEY') or 'dummy_key_for_tests'
        self.client: Client = Client(api_key=api_key)
        logger.info(f'GeminiClient initialized with model: {self.model_name}')

    @override
    async def chat(
        self,
        messages: list[dict[str, Any]],
        response_format: None | dict[str, Any] = None,
        temperature: float = 0.0,
        think: bool = False, # google genai does not support negating thinking, the models will always think
    ):
        # TODO: this is a temporary workaround, i need to define a proper abstract interface to unify the different LLM clients on a common interface, and then implement the chat method for each LLM client accordingly.
        assert messages[0]['role'] == 'system', 'The first message must be a system message.'
        assert messages[1]['role'] == 'user', 'The second message must be a user message.'

        contents = [
            types.Content(
                role='user',
                parts=[types.Part.from_text(text=messages[1]['content'])]
            )
        ]
        config: types.GenerateContentConfig = types.GenerateContentConfig(
            system_instruction=messages[0]['content'],
            temperature=temperature,
        )
        if response_format is not None:
            config.response_mime_type = 'application/json'
            config.response_schema = response_format

        logger.info(f'LLM chat request sent to {self.model_name}')
        logger.debug(f'Request contents: {json.dumps([content.model_dump(mode="json") for content in contents], indent=2)}')
        logger.debug(f'Request config: {json.dumps(config.model_dump(mode="json"), indent=2)}')
        response: types.GenerateContentResponse = await self.client.aio.models.generate_content(
            model=self.model_name,
            contents=contents,
            config=config
        )
        logger.info(f'LLM chat response received from {self.model_name}')
        logger.debug(f'Response data: {json.dumps(response.model_dump(mode="json"), indent=2)}')

        if response_format is None:
            return response.text
        else:
            return json.loads(response.text)

    @override
    async def agent(
        self,
        messages: list[dict[str, Any]],
        response_format: None | dict[str, Any] = None,
        temperature: float = 0.0,
        think: bool = False, # google genai does not support negating thinking, the models will always think
        mcp_client: fastmcp.Client | None = None,
    ):
        # TODO: this is a temporary workaround, i need to define a proper abstract interface to unify the different LLM clients on a common interface, and then implement the chat method for each LLM client accordingly.
        assert messages[0]['role'] == 'system', 'The first message must be a system message.'
        assert messages[1]['role'] == 'user', 'The second message must be a user message.'

        agent_loop_id: str = uuid.uuid4() # this is just fo logging purposes, however it could be later used to be stored in a database (it has to be better than this tho, maybe a uuid7)
        loop_count: int = 0 # this is just for logging purposes

        contents = [
            types.Content(
                role='user',
                parts=[types.Part.from_text(text=messages[1]['content'])]
            )
        ]

        config: types.GenerateContentConfig = types.GenerateContentConfig(
            system_instruction=messages[0]['content'],
            temperature=temperature,
        )
        if mcp_client is not None:
            tools_list = await mcp_client.list_tools()
            logger.info(f'(agent_loop={agent_loop_id}, model={self.model_name}), Prepared with tools: {len(tools_list)}')
            logger.debug(f'(agent_loop={agent_loop_id}, model={self.model_name}), Tools details: {json.dumps([tool.model_dump(mode="json") for tool in tools_list], indent=2)}')

            config.tools = tools_list
            config.automatic_function_calling = types.AutomaticFunctionCallingConfig(
                disable=True,
            )

        while True:
            loop_count += 1
            logger.info(f'(agent_loop={agent_loop_id}, loop_count={loop_count}, model={self.model_name}), Request sent')
            logger.debug(f'(agent_loop={agent_loop_id}, loop_count={loop_count}, model={self.model_name}), Request contents: {json.dumps([content.model_dump(mode="json") for content in contents], indent=2)}')
            logger.debug(f'(agent_loop={agent_loop_id}, loop_count={loop_count}, model={self.model_name}), Request config: {json.dumps(config.model_dump(mode="json"), indent=2)}')
            response: types.GenerateContentResponse = await self.client.aio.models.generate_content(
                model=self.model_name,
                contents=contents,
                config=config
            )
            logger.info(f'(agent_loop={agent_loop_id}, loop_count={loop_count}, model={self.model_name}), Response received')
            logger.debug(f'(agent_loop={agent_loop_id}, loop_count={loop_count}, model={self.model_name}), Response: {json.dumps(response.model_dump(mode="json"), indent=2)}')

            candidate: types.Candidate = response.candidates[0]
            model_parts: list[types.Part] = []
            tool_responses_parts: list[types.Part] = []
            logger.info(f'(agent_loop={agent_loop_id}, loop_count={loop_count}, model={self.model_name}), Requested tool calls count: {len([part for part in candidate.content.parts if part.function_call])}')
            logger.debug(f'(agent_loop={agent_loop_id}, loop_count={loop_count}, model={self.model_name}), Requested tool calls: {json.dumps([part.model_dump(mode="json") for part in candidate.content.parts if part.function_call], indent=2)}')

            for part in candidate.content.parts:
                if part.text:
                    model_parts.append(types.Part.from_text(text=part.text))
                elif part.function_call:
                    tool_call_id: str = part.function_call.id
                    tool_name: str = part.function_call.name
                    tool_args: dict[str, Any] = part.function_call.args
                    # we use getattr to avoid AttributeError in case the thought_signature is not present in the part, which can happen with old models that do not support thinking. In that case, we will just ignore the thought_signature and continue with the tool call.
                    thought_signature: bytes = getattr(part, 'thought_signature', None)
                    model_parts.append(
                        types.Part(
                            function_call=types.FunctionCall(
                                id=tool_call_id,
                                name=tool_name,
                                args=tool_args
                            ),
                            thought_signature=thought_signature
                        )
                    )

                    logger.info(f"(agent_loop={agent_loop_id}, loop_count={loop_count}, model={self.model_name}), Called tool: '{tool_name}'")
                    logger.debug(f"(agent_loop={agent_loop_id}, loop_count={loop_count}, model={self.model_name}), Tool args: {tool_name} ({tool_args})")
                    tool_result: CallToolResult = await mcp_client.call_tool(tool_name, tool_args)
                    logger.info(f"(agent_loop={agent_loop_id}, loop_count={loop_count}, model={self.model_name}), Tool returned: '{tool_name}'")
                    logger.debug(f"(agent_loop={agent_loop_id}, loop_count={loop_count}, model={self.model_name}), Tool result: {tool_name} -> {tool_result.content[0].text}")

                    tool_responses_parts.append(
                        types.Part.from_function_response(
                            name=tool_name,
                            response={'result': tool_result.content[0].text},
                        )
                    )

            contents.append(types.Content(role='model', parts=model_parts))
            if tool_responses_parts:
                contents.append(types.Content(role='user', parts=tool_responses_parts))
            else:
                logger.info(f"(agent_loop={agent_loop_id}, loop_count={loop_count}, model={self.model_name}), LLM did not request any tool calls")
                break

        if response_format is None:
            logger.info(f'(agent_loop={agent_loop_id}, model={self.model_name}), Response ready, no need to restructure')
            logger.debug(f'(agent_loop={agent_loop_id}, model={self.model_name}), Response: {response.text}')
            return response.text
        else:
            contents.append(types.Content(role='user', parts=[types.Part.from_text(text='Respond in a structured format')]))
            config = types.GenerateContentConfig(
                system_instruction=messages[0]['content'],
                temperature=temperature,
                response_mime_type='application/json',
                response_schema=response_format,
            )

            logger.info(f'(agent_loop={agent_loop_id}, model={self.model_name}), Restructure request sent')
            logger.debug(f'(agent_loop={agent_loop_id}, model={self.model_name}), Restructure request contents: {json.dumps([content.model_dump(mode="json") for content in contents], indent=2)}')
            logger.debug(f'(agent_loop={agent_loop_id}, model={self.model_name}), Restructure request config: {json.dumps(config.model_dump(mode="json"), indent=2)}')
            response = await self.client.aio.models.generate_content(
                model=self.model_name,
                contents=contents,
                config=config
            )
            result = json.loads(response.text)
            logger.info(f'(agent_loop={agent_loop_id}, model={self.model_name}), Restructure response received')
            logger.debug(f'(agent_loop={agent_loop_id}, model={self.model_name}), Restructure response: {json.dumps(response.model_dump(mode="json"), indent=2)}')

            logger.info(f'(agent_loop={agent_loop_id}, model={self.model_name}), Response ready, restructured')
            logger.debug(f'(agent_loop={agent_loop_id}, model={self.model_name}), Restructured response: {json.dumps(result, indent=2)}')

            return result
