
import asyncio
import json
import sys

from groq import Groq
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client


MODEL = "openai/gpt-oss-20b"
MAX_TOOL_CALLS = 8


def validate_arguments(tool, arguments):
    """Validate basic argument structure before calling MCP."""

    if not isinstance(arguments, dict):
        raise ValueError("Arguments must be a JSON object")

    schema = tool.input_schema
    properties = schema.get("properties", {})
    required = schema.get("required", [])

    # Handle the empty placeholder produced by Groq
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


async def main():
    question = input(
        "\nAsk your database a question: "
    ).strip()

    if not question:
        print("Please enter a question.")
        return

    server_params = StdioServerParameters(
        command=sys.executable,
        args=["server.py"],
    )

    async with stdio_client(server_params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            print("\nConnected to MCP server!")

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

            print("\nAvailable MCP tools:")
            for name in allowed_tools:
                print("-", name)

            client = Groq()

            messages = [
                {
                    "role": "system",
                    "content": (
                        "You are a read-only database assistant. "
                        "Use MCP tools to answer the user's question. "
                        "If needed, inspect tables and columns before "
                        "generating SQL. Use run_safe_query for data "
                        "questions. Never use SELECT *. "
                        "Never request sensitive columns. "
                        "Never invent data or claim a query succeeded "
                        "unless the MCP tool confirms it. "
                        "If a tool fails, explain the error or try "
                        "a different permitted approach. "
                        "Provide valid JSON tool arguments. "
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
                    print("\nGroq's final answer:")
                    print(
                        message.content
                        or "No answer was generated."
                    )
                    return

                # Preserve Groq's tool-call message
                messages.append(
                    message.model_dump(
                        exclude_none=True
                    )
                )

                for call in message.tool_calls:
                    tool_name = call.function.name

                    print(f"\nGroq selected: {tool_name}")
                    print(
                        "Arguments:",
                        call.function.arguments
                    )

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
                                    call.function.arguments
                                    or "{}"
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

                            except Exception as error:
                                tool_result = {
                                    "error": (
                                        "MCP tool execution failed: "
                                        f"{error}"
                                    )
                                }

                    print(
                        "MCP result:",
                        json.dumps(
                            tool_result,
                            ensure_ascii=False
                        )
                    )

                    # Return actual tool results to Groq
                    messages.append({
                        "role": "tool",
                        "tool_call_id": call.id,
                        "name": tool_name,
                        "content": json.dumps(
                            tool_result,
                            ensure_ascii=False
                        ),
                    })

            print(
                "\nStopped: Maximum MCP tool-call limit "
                "reached. No final answer was generated."
            )


if __name__ == "__main__":
    asyncio.run(main())
