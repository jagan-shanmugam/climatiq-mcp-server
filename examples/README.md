# Climatiq Examples

This directory contains example scripts and notebooks for interacting with the Climatiq API both directly and through the MCP server.

## Available Examples

### `climatiq.ipynb`

A Jupyter notebook demonstrating direct API usage with the Climatiq API. This notebook includes:

- Setting up your API key
- Searching for emission factors
- Calculating electricity emissions
- Calculating travel emissions
- Batch estimations
- Advanced travel calculations

To run this notebook:

1. Ensure you have Jupyter installed:
   ```bash
   uv pip install jupyter
   ```

2. Start Jupyter:
   ```bash
   jupyter notebook
   ```

3. Open the `climatiq.ipynb` file and follow the instructions inside

### `simple_test.py`

A simple Python script that tests the direct API integration with Climatiq without using the MCP protocol. This script:

- Configures logging
- Makes a direct API call to calculate electricity emissions
- Displays the results with emission factor details

To run this script:

```bash
# Make sure your API key is set in the environment
export CLIMATIQ_API_KEY=your_climatiq_api_key

# Run the script
python examples/simple_test.py
```

## Using These Examples

These examples are designed to help you understand how to interact with the Climatiq API directly, without the MCP protocol overhead. They're useful for:

1. **Testing your API key**: Make sure your Climatiq API key is working correctly
2. **Understanding the API**: See how the API requests and responses are structured
3. **Debugging**: If you're having issues with the MCP server, these examples can help isolate whether the problem is with the MCP implementation or the API itself

## Additional Notes

- The `simple_test.py` script requires the `aiohttp` and `python-dotenv` packages
- The Jupyter notebook requires additional packages like `requests` and `pandas`
- Both examples read the API key from the environment variable `CLIMATIQ_API_KEY` or from a `.env` file in the project root

## Next Steps

After exploring these examples, you might want to check out:

1. The MCP server implementation in `src/climatiq_mcp_server/`
2. The utility scripts in `utils/` directory, especially:
   - `climatiq_cli.py` for a command-line interface to the API
   - `test_client.py` for testing the MCP server implementation
   - `llm_example_client.py` for examples of how an LLM might interact with the MCP server 