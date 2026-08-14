import asyncio
import json
import os
from typing import Any, override

from dotenv import load_dotenv
import fastmcp
from fastmcp.client.client import CallToolResult
from google.genai import Client
from google.genai import types

load_dotenv()

from llm_service.llm_clients.llm_client import LLMClient

class GeminiClient(LLMClient):
    def __init__(self, model_name: str):
        self.model_name = model_name
        self.client: Client = Client(api_key=os.getenv('GEMINI_API_KEY'))

    @override
    async def chat(
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

        if mcp_client is not None:
            tools_list = await mcp_client.list_tools()

        contents = [
            types.Content(
                role='user',
                parts=[types.Part.from_text(text=messages[1]['content'])]
            )
        ]

        while True:
            response: types.GenerateContentResponse = await self.client.aio.models.generate_content(
                model=self.model_name,
                contents=contents,
                config=types.GenerateContentConfig(
                    system_instruction=messages[0]['content'],
                    temperature=temperature,
                    tools=tools_list,
                )
            )
            candidate: types.Candidate = response.candidates[0]
            model_parts: list[types.Part] = []
            tool_responses_parts: list[types.Part] = []
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

                    tool_result: CallToolResult = await mcp_client.call_tool(tool_name, tool_args)
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
                break

        if response_format is None:
            return response.text
        else:
            contents.append(types.Content(role='user', parts=[types.Part.from_text(text='Respond in a structured format')]))
            response = await self.client.aio.models.generate_content(
                model=self.model_name,
                contents=contents,
                config=types.GenerateContentConfig(
                    system_instruction=messages[0]['content'],
                    temperature=0.0,
                    response_mime_type='application/json',
                    response_schema=response_format,
                )
            )
            return json.loads(response.text)
