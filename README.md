# Climatiq MCP Server
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)&ensp;

A Model Context Protocol (MCP) server for accessing the Climatiq API to calculate carbon emissions. This allows AI assistants to perform real-time carbon calculations and provide climate impact insights.

## Demo


https://github.com/user-attachments/assets/c253d6d1-ccf6-4c14-965e-6023ba2a0296



https://github.com/user-attachments/assets/d61c1181-acf6-4d9f-9a48-537fc64ac4c3



## Features

This MCP server integrates with the Climatiq API to provide carbon emission calculations for AI assistants:

### Tools

- **set-api-key**: Configure the Climatiq API key used for authentication
- **electricity-emission**: Calculate carbon emissions from electricity consumption
- **travel-emission**: Calculate carbon emissions from travel by car, plane, or train
- **search-emission-factors**: Search for specific emission factors in the Climatiq database
- **custom-emission-calculation**: Perform custom calculations using specific emission factors
- **cloud-computing-emission**: Calculate emissions from cloud computing resources usage
- **freight-emission**: Calculate emissions from freight transportation
- **procurement-emission**: Calculate emissions from procurement spending
- **hotel-emission**: Calculate emissions from hotel stays
- **travel-spend**: Calculate emissions from travel expenses

### Resources

- Carbon calculation results are exposed as resources with a `climatiq://calculation/{id}` URI scheme
- Each resource contains detailed information about an emission factor and calculation results

### Prompts

- **climate-impact-explanation**: Generate natural language explanations about the climate impact of specific emission calculations

## Installation

### From Source

This project uses `uv` for virtual environment and dependency management. Make sure to [install uv](https://github.com/astral-sh/uv) first.

```bash
# Clone the repository
git clone https://github.com/your-org/climatiq-mcp-server.git
cd climatiq-mcp-server

# Create a virtual environment
uv venv

# Activate the virtual environment
# On macOS/Linux:
source .venv/bin/activate
# On Windows:
.venv\Scripts\activate

# Install dependencies with development extras
uv sync --dev --extra all
```

### Using uv

```bash
uv pip install climatiq-mcp-server
```

## API Key Configuration

The server requires a Climatiq API key to function. You have several options to provide it:

1. **Environment Variable**: Set the `CLIMATIQ_API_KEY` environment variable before starting the server
   ```bash
   export CLIMATIQ_API_KEY=your_climatiq_api_key
   ```

2. **Configuration During Installation**:
   ```bash
   CLIMATIQ_API_KEY=your_climatiq_api_key uv pip install climatiq-mcp-server
   ```

3. **set-api-key Tool**: Use the `set-api-key` tool to configure it during runtime within the AI assistant

4. **Configuration File**: Create a `.env` file in the project directory:
   ```
   CLIMATIQ_API_KEY=your_climatiq_api_key
   ```

To get a Climatiq API key:
1. Sign up at [app.climatiq.io](https://app.climatiq.io/api/signup)
2. Follow the instructions at [Getting API Keys](https://www.climatiq.io/docs/guides/how-tos/getting-api-key)

## Running the Server

The server can be started directly from the command line:

```bash
climatiq-mcp-server
```

## Setup in AI Assistants

### Claude Desktop

On MacOS: `~/Library/Application\ Support/Claude/claude_desktop_config.json`
On Windows: `%APPDATA%/Claude/claude_desktop_config.json`

<details>
  <summary>Configuration Example</summary>
  
  ```json
  "mcpServers": {
    "climatiq-mcp-server": {
      "command": "climatiq-mcp-server",
      "env": {
        "CLIMATIQ_API_KEY": "your_climatiq_api_key"
      }
    }
  }
  ```
</details>

## Examples and Utilities

### Examples Directory

The `examples/` directory contains:

- **climatiq.ipynb**: A Jupyter notebook demonstrating direct API usage with Climatiq
- **simple_test.py**: A simple utility for testing the API integration directly without MCP protocol

```bash
# Run the simple test
python examples/simple_test.py
```

### Utility Scripts

The `utils/` directory contains several helpful scripts:

#### Test Client

The `test_client.py` script tests all the tools, prompts, and resources:

```bash
python utils/test_client.py
```

#### LLM Example Client

The `llm_example_client.py` script demonstrates how a Large Language Model (like Claude) could interact with the Climatiq MCP server:

```bash
python utils/llm_example_client.py
```

Key features:
- Complete API wrapper with error handling and timeout management
- Resource and result caching to preserve calculation history
- Example prompts showing how to generate natural language explanations
- Demonstrates electricity emission, travel emission, and emission factor search capabilities

#### CLI Tool

A command-line interface tool for direct API access without the MCP server complexity:

```bash
# For electricity emissions
python utils/climatiq_cli.py electricity --energy 1000 --unit kWh --region US

# For travel emissions
python utils/climatiq_cli.py travel --mode car --distance 100 --unit km --region US
```

#### Run MCP Server Script

Use the `run_mcp_server.py` script to directly run the server without installing:

```bash
python utils/run_mcp_server.py
```

## Key Concepts

### Activity IDs

An Activity ID is a key concept in Climatiq's API that groups similar emission factors together:

- Each emission factor in the Climatiq database has an activity ID
- Activity IDs group emission factors describing the same activity across regions, years, sources, etc.
- Examples: `electricity-supply_grid-source_residual_mix` (electricity), `passenger_vehicle-vehicle_type_car` (car travel)

### Calculation Methods

The Climatiq MCP server supports multiple calculation methods:

1. **Distance-based method** for travel emissions
2. **Advanced travel calculations** with origin-destination pairs
3. **Spend-based method** for when you only have expenditure data
4. **Direct calculations** using specific emission factors

## Troubleshooting

### API Key Issues

1. Ensure `CLIMATIQ_API_KEY` is set correctly in your environment or .env file
2. Verify the API key is active in your Climatiq dashboard
3. Use `examples/simple_test.py` to check if your API key works correctly


## Advanced Usage

For detailed documentation on using specific tools and advanced features, see the [docs/README.md](docs/README.md) file.

## About Climatiq

Climatiq provides a powerful API for carbon intelligence, allowing you to calculate emissions from electricity usage, transportation, procurement, and more. This MCP server makes those capabilities accessible to AI assistants through the Model Context Protocol.

For more information about Climatiq, visit [climatiq.io](https://www.climatiq.io/).


## License
This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.