
# Guardrailed SQL & Database Explorer

## Project Overview
An AI-powered database explorer that allows users to
query an SQLite database using natural language.

The system integrates Groq AI with the Model Context
Protocol (MCP) and applies SQL security guardrails.

## Technologies Used
- Python
- Groq API (GPT-OSS 20B)
- Model Context Protocol (MCP)
- SQLite
- Streamlit
- SQLGlot

## Features
- Natural language to SQL
- Automatic MCP tool calling
- Database schema exploration
- SQL JOIN and aggregation queries
- Read-only database access
- Sensitive column protection
- SQL execution tracing
- Interactive database result tables

## Architecture

User
  |
  v
Streamlit Web Interface (app.py)
  |
  v
Groq AI Agent (database_agent.py)
  |
  v
MCP Server (server.py)
  |
  v
SQLite Database (shop.db)

## MCP Tools
1. list_tables
2. describe_table
3. get_sample_rows
4. run_safe_query

## Security
- Only SELECT queries are permitted
- DELETE, UPDATE and DROP are blocked
- Sensitive columns are protected
- SQL queries have execution time limits
- Result row limits are enforced
- Internal database tables are restricted

## How to Run

1. Activate the virtual environment:

   .\.venv\Scripts\Activate.ps1

2. Set the Groq API key in PowerShell:

   $env:GROQ_API_KEY = Read-Host "Enter Groq API key"

3. Start Streamlit:

   python -m streamlit run app.py

4. Open http://localhost:8501

## Testing

Run:

   python test_safe_query.py

The security test suite contains 19 tests.

## Example Questions

- Show all customer names.
- What tables are available?
- Show total spending by each customer.
- Describe the customers table.

## Conclusion

This project demonstrates how an LLM can interact
with a database through MCP while enforcing
SQL security restrictions.
