
import streamlit as st
import pandas as pd
import json
from database_agent import ask_database

st.set_page_config(
    page_title="Guardrailed SQL Explorer",
    page_icon="🛡️",
    layout="wide"
)

st.title("🛡️ Guardrailed SQL & Database Explorer")

st.write(
    "Ask questions about your SQLite database "
    "using Groq AI and MCP."
)

st.divider()

# Sidebar
with st.sidebar:
    st.header("⚙️ Project Information")

    st.write("**AI Model:** GPT-OSS 20B")
    st.write("**Provider:** Groq")
    st.write("**Database:** SQLite")
    st.write("**Protocol:** MCP")

    st.divider()
    st.info("🔒 Read-only database access")

    if st.button("🗑️ Clear Chat"):
        st.session_state.messages = []
        st.rerun()

# Initialize chat history
if "messages" not in st.session_state:
    st.session_state.messages = []


def display_trace(trace):
    """Display SQL queries, MCP tools and results."""

    if not trace:
        st.info("No MCP tools were executed.")
        return

    for index, step in enumerate(trace, start=1):

        tool_name = step["tool"]
        arguments = step["arguments"]
        result = step["result"]

        with st.expander(f"Step {index}: {tool_name}"):

            # Display executed SQL
            if tool_name == "run_safe_query":
                sql = arguments.get("sql")

                if sql:
                    st.write("**SQL Query:**")
                    st.code(sql, language="sql")

            st.write("**Tool Arguments:**")
            st.json(arguments)

            st.write("**MCP Result:**")
            st.json(result)

            # Display SQL results as a table
            if (
                tool_name == "run_safe_query"
                and not result.get("is_error")
                and not result.get("error")
            ):
                
                data = result.get("data", {})

                # MCP may return a list containing a JSON string
                if isinstance(data, list) and data:
                    data = data[0]

                # Convert JSON string into a Python dictionary
                if isinstance(data, str):
                    try:
                        data = json.loads(data)
                    except json.JSONDecodeError:
                        data = {}

                # Display database results
                if isinstance(data, dict):
                    rows = data.get("rows", [])

                    if isinstance(rows, list) and rows:
                        st.write("**Database Results:**")

                        st.dataframe(
                            pd.DataFrame(rows),
                            use_container_width=True,
                            hide_index=True
                        )

            if result.get("is_error") or result.get("error"):
                st.warning(
                    "This MCP tool returned an error "
                    "or rejected the request."
                )


def display_message(message):
    """Display chat message and optional MCP trace."""

    with st.chat_message(message["role"]):
        st.markdown(message["content"])

        if (
            message["role"] == "assistant"
            and "trace" in message
        ):
            with st.expander("🔍 View MCP Execution Trace"):
                display_trace(message["trace"])


# Display previous messages
for message in st.session_state.messages:
    display_message(message)


# Chat input
question = st.chat_input(
    "Ask your database a question..."
)

if question:

    user_message = {
        "role": "user",
        "content": question
    }

    st.session_state.messages.append(user_message)
    display_message(user_message)

    # Call Groq + MCP backend
    with st.spinner("Groq is querying your database..."):

        try:
            response = ask_database(
                question,
                include_trace=True
            )

            assistant_message = {
                "role": "assistant",
                "content": response["answer"],
                "trace": response["trace"]
            }

        except Exception as error:
            assistant_message = {
                "role": "assistant",
                "content": (
                    "Unable to process your request. "
                    "Check the terminal for details."
                ),
                "trace": []
            }

            st.error(str(error))

    st.session_state.messages.append(
        assistant_message
    )

    display_message(assistant_message)
