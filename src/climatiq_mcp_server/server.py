import asyncio
import os
import json
import logging
from typing import Optional, Dict, Any, List
import httpx
import signal
import sys

from mcp.server.models import InitializationOptions
import mcp.types as types
from mcp.server import NotificationOptions, Server
from pydantic import AnyUrl
import mcp.server.stdio

# Configure logging
logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)

# Create console handler with a higher log level
ch = logging.StreamHandler()
ch.setLevel(logging.DEBUG)

# Create formatter
formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
ch.setFormatter(formatter)

# Add the handlers to logger
logger.addHandler(ch)

# Import tools
from climatiq_mcp_server.tools import (
    set_api_key_tool,
    electricity_emission_tool,
    travel_emission_tool,
    search_emission_factors_tool,
    custom_emission_calculation_tool,
    cloud_computing_emission_tool,
    freight_emission_tool,
    procurement_emission_tool,
    hotel_emission_tool,
    travel_spend_tool,
    get_tool_definitions
)

# Store API key and configurations
config = {
    "api_key": os.environ.get("CLIMATIQ_API_KEY", ""),
    "base_url": "https://api.climatiq.io",
    "data_version": "^6"  # Default data version
}

# Store cached emission factor results
cached_results: dict[str, dict] = {}

server = Server("climatiq-mcp-server")

# Helper function to make requests to Climatiq API
async def climatiq_request(endpoint: str, json_data: dict, method: str = "POST") -> dict:
    """Make a request to the Climatiq API."""
    if not config["api_key"]:
        raise ValueError("Climatiq API key not set. Please configure it using the set-api-key tool.")
    
    url = f"{config['base_url']}{endpoint}"
    headers = {
        "Authorization": f"Bearer {config['api_key']}",
        "Content-Type": "application/json"
    }

    logger.debug(f"Request URL: {url}")
    logger.debug(f"Request method: {method}")
    logger.debug(f"Request headers: {headers}")
    logger.debug(f"Request data: {json.dumps(json_data, indent=2)}")
    
    try:
        async with httpx.AsyncClient(timeout=60.0) as client:
            if method.upper() == "POST":
                response = await client.post(url, headers=headers, json=json_data)
            else:
                response = await client.get(url, headers=headers, params=json_data)
            
            logger.debug(f"Response status code: {response.status_code}")
            
            if response.status_code != 200:
                error_detail = response.text
                try:
                    error_json = response.json()
                    if "error" in error_json:
                        error_detail = error_json["error"]
                    elif "message" in error_json:
                        error_detail = error_json["message"]
                except:
                    pass
                
                logger.error(f"API request failed with status {response.status_code}: {error_detail}")
                raise ValueError(f"API request failed with status {response.status_code}: {error_detail}")
            
            result = response.json()
            logger.debug(f"Response data: {json.dumps(result, indent=2)}")
            return result
    except httpx.TimeoutException:
        logger.error("Request to Climatiq API timed out")
        raise ValueError("Request to Climatiq API timed out. Please try again later.")
    except httpx.RequestError as e:
        logger.error(f"Request error: {str(e)}")
        raise ValueError(f"Failed to connect to Climatiq API: {str(e)}")
    except Exception as e:
        logger.error(f"Unexpected error during API request: {str(e)}", exc_info=True)
        raise ValueError(f"Error during Climatiq API request: {str(e)}")

@server.list_resources()
async def handle_list_resources() -> list[types.Resource]:
    """
    List available resources including cached results.
    """
    resources = []
    
    # Add cached emission calculation results
    for cache_id, result in cached_results.items():
        if "co2e" in result and "emission_factor" in result:
            name = result.get("emission_factor", {}).get("name", "Unknown emission factor")
            resources.append(
                types.Resource(
                    uri=AnyUrl(f"climatiq://calculation/{cache_id}"),
                    name=f"Calculation: {name}",
                    description=f"CO2e: {result.get('co2e')} {result.get('co2e_unit', 'kg')}",
                    mimeType="application/json",
                )
            )
    
    return resources

@server.read_resource()
async def handle_read_resource(uri: AnyUrl) -> str:
    """
    Read a specific calculation result by its URI.
    """
    if uri.scheme != "climatiq":
        raise ValueError(f"Unsupported URI scheme: {uri.scheme}")

    path_parts = uri.path.lstrip("/").split("/")
    if len(path_parts) < 2 or path_parts[0] != "calculation":
        raise ValueError(f"Invalid resource path: {uri.path}")
        
    cache_id = path_parts[1]
    if cache_id not in cached_results:
        raise ValueError(f"Calculation result not found: {cache_id}")
    
    return json.dumps(cached_results[cache_id], indent=2)

@server.list_prompts()
async def handle_list_prompts() -> list[types.Prompt]:
    """
    List available prompts.
    """
    return [
        types.Prompt(
            name="climate-impact-explanation",
            description="Explains the climate impact of a specific emission calculation",
            arguments=[
                types.PromptArgument(
                    name="calculation_id",
                    description="ID of the cached calculation result to explain",
                    required=True,
                ),
                types.PromptArgument(
                    name="detail_level",
                    description="Level of detail (basic/detailed)",
                    required=False,
                )
            ],
        )
    ]

@server.get_prompt()
async def handle_get_prompt(
    name: str, arguments: dict[str, str] | None
) -> types.GetPromptResult:
    """
    Generate a prompt explaining climate impact.
    """
    if name != "climate-impact-explanation":
        raise ValueError(f"Unknown prompt: {name}")

    if not arguments or "calculation_id" not in arguments:
        raise ValueError("Missing required argument: calculation_id")
        
    calculation_id = arguments["calculation_id"]
    if calculation_id not in cached_results:
        raise ValueError(f"Calculation result not found: {calculation_id}")
        
    result = cached_results[calculation_id]
    detail_level = arguments.get("detail_level", "basic")
    
    # Format the result information for the prompt
    co2e = result.get("co2e", 0)
    co2e_unit = result.get("co2e_unit", "kg")
    emission_factor = result.get("emission_factor", {})
    activity_data = result.get("activity_data", {})
    
    detail_text = ""
    if detail_level == "detailed":
        detail_text = "\n\nPlease provide a detailed analysis including comparisons to everyday activities and detailed explanation of the environmental impact."
    
    return types.GetPromptResult(
        description=f"Explaining climate impact of {emission_factor.get('name', 'the activity')}",
        messages=[
            types.PromptMessage(
                role="user",
                content=types.TextContent(
                    type="text",
                    text=f"Please explain the climate impact of this emission calculation in simple terms:{detail_text}\n\n"
                         f"Activity: {emission_factor.get('name', 'Unknown activity')}\n"
                         f"Value: {activity_data.get('activity_value', 'Unknown')} {activity_data.get('activity_unit', '')}\n"
                         f"Carbon footprint: {co2e} {co2e_unit} CO2e\n"
                         f"Region: {emission_factor.get('region', 'Unknown')}\n"
                         f"Year: {emission_factor.get('year', 'Unknown')}\n"
                         f"Source: {emission_factor.get('source', 'Unknown')}"
                ),
            )
        ],
    )

@server.list_tools()
async def handle_list_tools() -> list[types.Tool]:
    """
    List available tools for interacting with the Climatiq API.
    """
    return get_tool_definitions()

@server.call_tool()
async def handle_call_tool(
    name: str, arguments: dict | None
) -> list[types.TextContent | types.ImageContent | types.EmbeddedResource]:
    """
    Handle tool execution requests for Climatiq API operations.
    """
    if not arguments:
        raise ValueError("Missing arguments")

    result_text = ""
    result = None
    cache_id = None
    
    # Route to the appropriate tool handler
    if name == "set-api-key":
        result_text = await set_api_key_tool(config, arguments, server, climatiq_request)
    elif name == "electricity-emission":
        result_text, result, cache_id = await electricity_emission_tool(config, arguments, server, climatiq_request)
    elif name == "travel-emission":
        result_text, result, cache_id = await travel_emission_tool(config, arguments, server, climatiq_request)
    elif name == "search-emission-factors":
        result_text, result, cache_id = await search_emission_factors_tool(config, arguments, server, climatiq_request)
    elif name == "custom-emission-calculation":
        result_text, result, cache_id = await custom_emission_calculation_tool(config, arguments, server, climatiq_request)
    elif name == "cloud-computing-emission":
        result_text, result, cache_id = await cloud_computing_emission_tool(config, arguments, server, climatiq_request)
    elif name == "freight-emission":
        result_text, result, cache_id = await freight_emission_tool(config, arguments, server, climatiq_request)
    elif name == "procurement-emission":
        result_text, result, cache_id = await procurement_emission_tool(config, arguments, server, climatiq_request)
    elif name == "hotel-emission":
        result_text, result, cache_id = await hotel_emission_tool(config, arguments, server, climatiq_request)
    elif name == "travel-spend":
        result_text, result, cache_id = await travel_spend_tool(config, arguments, server, climatiq_request)
    else:
        raise ValueError(f"Unknown tool: {name}")

    # Store result in cache if available
    if result and cache_id:
        cached_results[cache_id] = result
        # Don't send notification to avoid potential issues during testing
        # await server.request_context.session.send_resource_list_changed()

    return [
        types.TextContent(
            type="text",
            text=result_text,
        )
    ]

async def main():
    """Run the server using stdin/stdout streams."""
    try:
        logger.info("Starting Climatiq MCP Server")
        logger.info(f"API Key: {'Configured' if config['api_key'] else 'Not configured'}")
        logger.info(f"Base URL: {config['base_url']}")
        logger.info(f"Data Version: {config['data_version']}")
        
        # Set up signal handlers for graceful shutdown
        for signal_name in ('SIGINT', 'SIGTERM'):
            try:
                loop = asyncio.get_running_loop()
                loop.add_signal_handler(
                    getattr(signal, signal_name),
                    lambda: logger.info(f"Received {signal_name}, shutting down gracefully...")
                )
            except (NotImplementedError, ImportError):
                # Windows doesn't support UNIX signals
                pass
                
        # Run the server using stdin/stdout streams
        async with mcp.server.stdio.stdio_server() as (read_stream, write_stream):
            await server.run(
                read_stream,
                write_stream,
                InitializationOptions(
                    server_name="climatiq-mcp-server",
                    server_version="0.2.0",
                    capabilities=server.get_capabilities(
                        notification_options=NotificationOptions(),
                        experimental_capabilities={},
                    ),
                ),
            )
    except Exception as e:
        logger.exception(f"Fatal error in Climatiq MCP server: {str(e)}")
        raise
    finally:
        logger.info("Climatiq MCP server shutting down")

def run_server():
    """Entry point function that runs the main coroutine."""
    try:
        # Import signal module for shutdown handling
        import signal
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Server interrupted by user")
    except Exception as e:
        logger.exception(f"Unhandled error: {str(e)}")
        sys.exit(1)

if __name__ == "__main__":
    run_server()