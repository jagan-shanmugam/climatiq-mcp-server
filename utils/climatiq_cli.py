#!/usr/bin/env python
"""
Climatiq CLI - A simple command line interface for Climatiq API

This script provides a simple way to calculate emissions using the Climatiq API
without the complexity of the MCP server protocol.
"""
import os
import sys
import json
import argparse
import asyncio
import logging
from pathlib import Path

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

# Add the src directory to Python path
sys.path.insert(0, str(Path(__file__).parent.parent))

# Import the climatiq_request function from the server module
from climatiq_mcp_server.server import climatiq_request

# Configuration
config = {
    "api_key": os.environ.get("CLIMATIQ_API_KEY", ""),
    "base_url": "https://api.climatiq.io",
    "data_version": "^6"
}

async def calculate_electricity_emission(energy, energy_unit, region):
    """Calculate emissions from electricity consumption"""
    logger.info(f"Calculating emissions for {energy} {energy_unit} of electricity in {region}")
    
    # Construct request data
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
    
    # Make the API request
    result = await climatiq_request("/data/v1/estimate", request_data)
    
    # Format the result
    co2e = result.get("co2e", 0)
    co2e_unit = result.get("co2e_unit", "kg")
    
    # Create a user-friendly output
    output = f"\nElectricity consumption of {energy} {energy_unit} in {region} results in {co2e} {co2e_unit} of CO2e emissions.\n"
    
    if "emission_factor" in result and result["emission_factor"].get("name"):
        ef_name = result["emission_factor"]["name"]
        output += f"Emission factor used: {ef_name}\n"
    
    # Add source information
    if "emission_factor" in result:
        ef = result["emission_factor"]
        if "source" in ef:
            output += f"Source: {ef.get('source')}"
            if "source_dataset" in ef:
                output += f" - {ef.get('source_dataset')}"
            output += "\n"
        if "year" in ef:
            output += f"Year of data: {ef.get('year')}\n"
            
    print(output)
    
    # Ask if user wants to see the full JSON response
    if input("Would you like to see the full API response? (y/n): ").lower() == 'y':
        print(json.dumps(result, indent=2))
    
    return result

async def calculate_travel_emission(mode, distance, distance_unit, region="US"):
    """Calculate emissions from travel"""
    logger.info(f"Calculating emissions for {distance} {distance_unit} of {mode} travel in {region}")
    
    # Map mode to activity ID
    mode_mapping = {
        "car": "passenger_vehicle-vehicle_type_car-fuel_source_na-engine_size_na-vehicle_age_na-vehicle_weight_na",
        "plane": "passenger_flight-route_type_international-aircraft_type_na-distance_na-class_na-rf_included",
        "train": "passenger_train-route_type_commuter_rail-fuel_source_na"
    }
    
    if mode.lower() not in mode_mapping:
        print(f"Unsupported travel mode: {mode}. Supported modes are: car, plane, train")
        return None
    
    # Construct request data
    request_data = {
        "emission_factor": {
            "activity_id": mode_mapping[mode.lower()],
            "data_version": config["data_version"],
            "region": region
        },
        "parameters": {
            "distance": distance,
            "distance_unit": distance_unit
        }
    }
    
    # Make the API request
    result = await climatiq_request("/data/v1/estimate", request_data)
    
    # Format the result
    co2e = result.get("co2e", 0)
    co2e_unit = result.get("co2e_unit", "kg")
    
    # Create a user-friendly output
    output = f"\n{mode.capitalize()} travel of {distance} {distance_unit} in {region} results in {co2e} {co2e_unit} of CO2e emissions.\n"
    
    if "emission_factor" in result and result["emission_factor"].get("name"):
        ef_name = result["emission_factor"]["name"]
        output += f"Emission factor used: {ef_name}\n"
    
    # Add source information
    if "emission_factor" in result:
        ef = result["emission_factor"]
        if "source" in ef:
            output += f"Source: {ef.get('source')}"
            if "source_dataset" in ef:
                output += f" - {ef.get('source_dataset')}"
            output += "\n"
        if "year" in ef:
            output += f"Year of data: {ef.get('year')}\n"
            
    print(output)
    
    # Ask if user wants to see the full JSON response
    if input("Would you like to see the full API response? (y/n): ").lower() == 'y':
        print(json.dumps(result, indent=2))
    
    return result

async def main():
    """Main entry point for the CLI"""
    parser = argparse.ArgumentParser(description="Climatiq CLI - Calculate carbon emissions")
    subparsers = parser.add_subparsers(dest="command", help="Command to run")
    
    # Electricity command
    electricity_parser = subparsers.add_parser("electricity", help="Calculate emissions from electricity consumption")
    electricity_parser.add_argument("--energy", "-e", type=float, required=True, help="Amount of energy consumed")
    electricity_parser.add_argument("--unit", "-u", default="kWh", help="Energy unit (default: kWh)")
    electricity_parser.add_argument("--region", "-r", default="US", help="Region code (default: US)")
    
    # Travel command
    travel_parser = subparsers.add_parser("travel", help="Calculate emissions from travel")
    travel_parser.add_argument("--mode", "-m", required=True, choices=["car", "plane", "train"], help="Travel mode")
    travel_parser.add_argument("--distance", "-d", type=float, required=True, help="Distance traveled")
    travel_parser.add_argument("--unit", "-u", default="km", help="Distance unit (default: km)")
    travel_parser.add_argument("--region", "-r", default="US", help="Region code (default: US)")
    
    # Parse arguments
    args = parser.parse_args()
    
    # Check for API key
    if not config["api_key"]:
        print("Error: CLIMATIQ_API_KEY environment variable not set")
        print("Please set it before running: export CLIMATIQ_API_KEY=your_api_key")
        return 1
    
    # Execute the appropriate command
    if args.command == "electricity":
        await calculate_electricity_emission(args.energy, args.unit, args.region)
    elif args.command == "travel":
        await calculate_travel_emission(args.mode, args.distance, args.unit, args.region)
    else:
        parser.print_help()
        return 1
    
    return 0

if __name__ == "__main__":
    try:
        exit_code = asyncio.run(main())
        sys.exit(exit_code)
    except KeyboardInterrupt:
        print("\nOperation cancelled by user")
        sys.exit(1)
    except Exception as e:
        print(f"Error: {str(e)}")
        sys.exit(1) 