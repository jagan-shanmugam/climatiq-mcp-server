# Climatiq Utility Scripts

This directory contains several utility scripts to help test, run, and interact with the Climatiq API and MCP server.

## Available Utilities

### `test_client.py`

A comprehensive test client that connects to the MCP server and tests all tools, prompts, and resources.

Features:
- Starts the MCP server as a subprocess (if not already running)
- Tests all available tools with sample parameters
- Examines resources created during tool execution
- Tests the climate-impact-explanation prompt with calculation results

Usage:
```bash
python utils/test_client.py
```

### `llm_example_client.py`

Demonstrates how a Large Language Model (like Claude) could interact with the Climatiq MCP server.

Features:
- `ClimatiqAssistant` class that wraps the MCP client for easier integration with LLMs
- Helper methods for all Climatiq tools with proper parameter handling
- Example conversation flows for different carbon calculation scenarios
- Methods to obtain and explain detailed climate impact information

Usage:
```bash
python utils/llm_example_client.py
```

### `climatiq_cli.py`

A command-line interface tool for direct API access without the MCP protocol overhead.

Features:
- Direct API requests to Climatiq
- Simple interface for common emission calculations
- User-friendly results with detailed information about emission factors
- Option to view the full JSON API response

Usage:
```bash
# For electricity emissions
python utils/climatiq_cli.py electricity --energy 1000 --unit kWh --region US

# For travel emissions
python utils/climatiq_cli.py travel --mode car --distance 100 --unit km --region US

# For search
python utils/climatiq_cli.py search --query "grid mix" --region US
```

### `run_mcp_server.py`

A simple script to run the MCP server directly without installing the package.

Features:
- Adds the source directory to the Python path
- Runs the server's main function directly
- Useful for development and testing

Usage:
```bash
python utils/run_mcp_server.py
```

## Common Use Cases

### Verifying API Integration

If you're having issues with the MCP server, you can use these utilities to isolate the problem:

1. Use `climatiq_cli.py` to verify direct API access
2. Use `test_client.py` to test the MCP server implementation
3. Use `llm_example_client.py` to test specific LLM interaction patterns

### Development and Testing

During development:

1. Run the MCP server with `run_mcp_server.py`
2. Test your changes with `test_client.py`
3. Use `llm_example_client.py` to see how your changes affect LLM interactions

## Requirements

These utilities require the same dependencies as the main package:

- `aiohttp`
- `async-timeout`
- `python-dotenv`
- `pydantic`
- `modelcontextprotocol` (for MCP-related utilities)

Most of these are installed automatically when you set up the environment using:

```bash
# Create a virtual environment
uv venv

# Activate the environment
source .venv/bin/activate  # On Windows: .venv\Scripts\activate

# Install dependencies with development extras
uv sync --dev --extras
```
