#!/usr/bin/env python3
"""
Simple script to run the Climatiq MCP server directly.
This avoids issues with the MCP CLI command structure.
"""

import asyncio
import os
import sys

# Add the src directory to the Python path if needed
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "src")))

# Import the main function from the server module
from climatiq_mcp_server.server import main

if __name__ == "__main__":
    # Set API key from environment if provided
    api_key = os.environ.get("CLIMATIQ_API_KEY")
    if api_key:
        print(f"Using API key from environment variable", file=sys.stderr)
    else:
        print(f"Warning: No API key found in environment variables", file=sys.stderr)
    
    # Run the server
    asyncio.run(main()) 