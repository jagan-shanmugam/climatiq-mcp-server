#!/usr/bin/env python
"""
Simple test utility for Climatiq tools
This is a standalone script to test the Climatiq API integration directly
without the complexity of MCP server protocol
"""
import os
import asyncio
import json
import logging
import sys
from pathlib import Path

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)]
)
logger = logging.getLogger(__name__)

# Add the src directory to Python path
sys.path.insert(0, str(Path(__file__).parent.parent))

# Import the necessary functions
from climatiq_mcp_server.server import climatiq_request

# Test config
config = {
    "api_key": os.environ.get("CLIMATIQ_API_KEY", ""),
    "base_url": "https://api.climatiq.io",
    "data_version": "^6"
}

async def test_electricity_emission():
    """
    Test the electricity emission calculation directly using the Climatiq API
    """
    logger.info("Testing electricity emission calculation")
    
    # Parameters for the test
    energy = 1000
    energy_unit = "kWh"
    region = "US"
    
    # Construct request data (copied from the tool implementation)
    request_data = {
        "emission_factor": {
            "activity_id": "electricity-supply_grid-source_residual_mix",
            "data_version": config["data_version"],
            "region": region
        },
        "parameters": {
            "energy": energy,
            "energy_unit": energy_unit
        }
    }
    
    try:
        # Make the API request
        result = await climatiq_request("/data/v1/estimate", request_data)
        
        # Process the result
        co2e = result.get("co2e", 0)
        co2e_unit = result.get("co2e_unit", "kg")
        
        logger.info(f"Result: Electricity consumption of {energy} {energy_unit} in {region} results in {co2e} {co2e_unit} of CO2e emissions")
        
        # Pretty print the full result
        logger.info(f"Full API response: {json.dumps(result, indent=2)}")
        
        logger.info("Test completed successfully!")
        return True
    except Exception as e:
        logger.error(f"Test failed: {str(e)}")
        return False

async def main():
    """Main entry point for the test utility"""
    # Check if API key is set
    if not config["api_key"]:
        logger.error("CLIMATIQ_API_KEY environment variable not set")
        logger.info("Please set it before running the test: export CLIMATIQ_API_KEY=your_api_key")
        return False
    
    logger.info("Starting simple Climatiq API test")
    logger.info(f"API Key: {'Set' if config['api_key'] else 'Not set'}")
    logger.info(f"Base URL: {config['base_url']}")
    logger.info(f"Data Version: {config['data_version']}")
    
    # Run the test
    success = await test_electricity_emission()
    
    if success:
        logger.info("All tests completed successfully!")
        return True
    else:
        logger.error("Tests failed!")
        return False

if __name__ == "__main__":
    success = asyncio.run(main())
    sys.exit(0 if success else 1) 