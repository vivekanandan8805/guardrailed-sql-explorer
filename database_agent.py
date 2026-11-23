
import asyncio
import json
import sys
from pathlib import Path

from groq import Groq
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client


MODEL = "openai/gpt-oss-20b"
MAX_TOOL_CALLS = 8

PROJECT_DIR = Path(__file__).resolve().parent


def validate_arguments(tool, arguments):
    """Validate basic MCP tool arguments."""

    if not isinstance(arguments, dict):
        raise ValueError("Arguments must be a JSON object")

    schema = tool.input_schema
    properties = schema.get("properties", {})
    required = schema.get("required", [])

    if (
        not properties
        and not required
        and arguments == {"": ""}
    ):
        arguments = {}

    unexpected = set(arguments) - set(properties)

    if unexpected:
        raise ValueError(
            f"Unexpected arguments: {sorted(unexpected)}"
        )

    missing = set(required) - set(arguments)

    if missing:
        raise ValueError(
            f"Missing required arguments: {sorted(missing)}"
        )

    return arguments


def extract_result(result):
    """Convert MCP results into JSON-compatible data."""

    if result.structured_content is not None:
        return result.structured_content

    return [
        item.text
        for item in result.content
        if item.type == "text"
    ]


async def ask_database_async(question, include_trace=False):
    """Ask Groq a question using MCP tools."""

    trace = []

    def make_response(answer):
        if include_trace:
            return {
                "answer": answer,
                "trace": trace
            }
        return answer

    if not question or not question.strip():
        return make_response(
            "Please enter a database question."
        )

    server_params = StdioServerParameters(
        command=sys.executable,
        args=[str(PROJECT_DIR / "server.py")],
        cwd=str(PROJECT_DIR),
    )

    async with stdio_client(server_params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()

            response = await session.list_tools()

            allowed_tools = {
                tool.name: tool
                for tool in response.tools
            }

            groq_tools = [
                {
                    "type": "function",
                    "function": {
                        "name": tool.name,
                        "description": tool.description or "",
                        "parameters": tool.input_schema,
                    },
                }
                for tool in response.tools
            ]

            client = Groq()

            messages = [
                {
                    "role": "system",
                    "content": (
                        "You are a read-only database assistant. "
                        "Answer database questions using MCP tools. "
                        "Inspect schemas when needed. "
                        "Use run_safe_query for database queries. "
                        "Never use SELECT *. "
                        "Never request sensitive columns. "
                        "Never invent database results. "
                        "If a tool fails, explain the error or "
                        "try another permitted approach. "
                        "Use valid JSON tool arguments. "
                        "Keep answers concise."
                    ),
                },
                {
                    "role": "user",
                    "content": question,
                },
            ]

            tool_calls_used = 0

            while tool_calls_used < MAX_TOOL_CALLS:

                completion = client.chat.completions.create(
                    model=MODEL,
                    messages=messages,
                    tools=groq_tools,
                    tool_choice="auto",
                )

                message = completion.choices[0].message

                if not message.tool_calls:
                    answer = (
                        message.content
                        or "No answer was generated."
                    )
                    return make_response(answer)

                messages.append(
                    message.model_dump(exclude_none=True)
                )

                for call in message.tool_calls:

                    tool_name = call.function.name
                    arguments = {}

                    if tool_calls_used >= MAX_TOOL_CALLS:
                        tool_result = {
                            "error": "Tool-call limit reached"
                        }

                    else:
                        tool_calls_used += 1

                        if tool_name not in allowed_tools:
                            tool_result = {
                                "error": "Unknown MCP tool"
                            }

                        else:
                            try:
                                arguments = json.loads(
                                    call.function.arguments or "{}"
                                )

                                arguments = validate_arguments(
                                    allowed_tools[tool_name],
                                    arguments,
                                )

                                result = await session.call_tool(
                                    tool_name,
                                    arguments=arguments,
                                )

                                tool_result = {
                                    "is_error": result.is_error,
                                    "data": extract_result(result),
                                }

                            except (
                                ValueError,
                                TypeError,
                                json.JSONDecodeError,
                            ) as error:
                                tool_result = {
                                    "error": str(error)
                                }

                            except Exception:
                                tool_result = {
                                    "error": "MCP tool execution failed"
                                }

                    # Record MCP execution details
                    trace.append({
                        "tool": tool_name,
                        "arguments": arguments,
                        "result": tool_result,
                    })

                    # Return MCP result to Groq
                    messages.append({
                        "role": "tool",
                        "tool_call_id": call.id,
                        "name": tool_name,
                        "content": json.dumps(
                            tool_result,
                            ensure_ascii=False
                        ),
                    })

            return make_response(
                "Maximum MCP tool-call limit reached."
            )


def ask_database(question, include_trace=False):
    """Synchronous wrapper for Streamlit."""

    return asyncio.run(
        ask_database_async(
            question,
            include_trace=include_trace
        )
    )


if __name__ == "__main__":

    question = input("Ask your database: ")

    response = ask_database(
        question,
        include_trace=True
    )

    print("\nAnswer:")
    print(response["answer"])

    print("\nMCP Execution Trace:")
    print(
        json.dumps(
            response["trace"],
            indent=2,
            ensure_ascii=False
        )
    )
