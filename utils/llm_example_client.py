#!/usr/bin/env python3
"""
LLM Example Client for the Climatiq MCP server.

This script demonstrates how a large language model could interact with
the Climatiq MCP server to perform carbon emissions calculations and
provide climate impact information to users.
"""

import asyncio
import json
import os
import sys
from pathlib import Path
from contextlib import AsyncExitStack
from datetime import datetime
from dotenv import load_dotenv
import logging

# MCP client library imports
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

# Add the src directory to the Python path if needed
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

# Load API key from .env file
dotenv_path = Path(os.getcwd()) / '.env'
load_dotenv(dotenv_path=dotenv_path)
CLIMATIQ_API_KEY = os.getenv("CLIMATIQ_API_KEY")

# Configure logging
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

# Create console handler with a higher log level
ch = logging.StreamHandler()
ch.setLevel(logging.INFO)

# Create formatter
formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
ch.setFormatter(formatter)

# Add the handlers to logger
logger.addHandler(ch)

class ClimatiqAssistant:
    """A helper class that allows an LLM to interact with Climatiq carbon calculation services"""
    
    def __init__(self, api_key=None, python_executable=None):
        self.api_key = api_key or CLIMATIQ_API_KEY
        self.python_executable = python_executable or sys.executable
        
        self.server_params = StdioServerParameters(
            command=self.python_executable,
            args=["-c", "from climatiq_mcp_server.server import run_server; import asyncio; asyncio.run(run_server())"],
            env={"CLIMATIQ_API_KEY": self.api_key} if self.api_key else None
        )
        self.session = None
        self.exit_stack = AsyncExitStack()
        
    async def __aenter__(self):
        """Setup the connection when entering the context manager"""
        try:
            # Use AsyncExitStack to properly manage resources
            stdio_transport = await self.exit_stack.enter_async_context(stdio_client(self.server_params))
            self.read, self.write = stdio_transport
            self.session = await self.exit_stack.enter_async_context(ClientSession(self.read, self.write))
            
            # Initialize the session with a timeout
            await asyncio.wait_for(self.session.initialize(), timeout=30.0)
            
            return self
        except Exception as e:
            logger.error(f"Error initializing Climatiq Assistant: {e}")
            # Ensure resources are cleaned up if initialization fails
            await self.exit_stack.aclose()
            raise
        
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Close the connection when exiting the context manager"""
        await self.exit_stack.aclose()
        
    def _parse_text_content(self, result):
        """Helper to parse text from TextContent"""
        if not result or not result.content:
            return ""
            
        result_text = ""
        for content_item in result.content:
            if content_item.type == 'text':
                result_text += content_item.text
                
        return result_text
        
    def _parse_json_content(self, result):
        """Helper to parse JSON from TextContent"""
        text_content = self._parse_text_content(result)
        if not text_content:
            return None
            
        try:
            return json.loads(text_content)
        except json.JSONDecodeError:
            return {"text": text_content}
        
    async def set_api_key(self, api_key):
        """Set the Climatiq API key if not provided in the environment"""
        result = await self.session.call_tool(
            "set-api-key", 
            {"api_key": api_key}
        )
        return self._parse_text_content(result)
    
    async def calculate_electricity_emission(self, energy, energy_unit="kWh", region="US"):
        """Calculate carbon emissions from electricity consumption"""
        try:
            logger.debug(f"Electricity emission request: energy={energy}, unit={energy_unit}, region={region}")
            result = await self.session.call_tool(
                "electricity-emission", 
                {
                    "energy": energy,
                    "energy_unit": energy_unit,
                    "region": region
                }
            )
            
            return self._parse_text_content(result)
        except Exception as e:
            logger.error(f"Error in electricity emission calculation: {e}")
            return f"Error calculating electricity emissions: {e}"
    
    async def calculate_travel_emission(self, mode, distance=None, distance_unit="km", passengers=1, vehicle_type="medium", fuel_type="regular", origin=None, destination=None, year=None, car_details=None, air_details=None):
        """Calculate carbon emissions from travel"""
        params = {
            "mode": mode
        }
        
        # Either set distance or origin-destination pair
        if distance is not None:
            params["distance"] = distance
            params["distance_unit"] = distance_unit
        elif origin and destination:
            params["origin"] = origin
            params["destination"] = destination
        else:
            raise ValueError("Either distance or both origin and destination must be provided")
        
        # Add optional parameters - simplified to match API requirements
        if mode.lower() == "car" and vehicle_type:
            params["vehicle_type"] = vehicle_type
            
            # Only add these if they're actually needed by the API
            if fuel_type and fuel_type != "regular":
                params["fuel_type"] = fuel_type
            if passengers and passengers > 1:
                params["passengers"] = passengers
        elif mode.lower() in ["plane", "aircraft", "flight"] and vehicle_type:
            params["vehicle_type"] = vehicle_type
        elif mode.lower() in ["train", "rail"] and vehicle_type:
            params["vehicle_type"] = vehicle_type
        
        if year:
            params["year"] = year
        
        # Log the request for debugging
        logger.debug(f"Travel emission request: {params}")
        
        try:
            result = await self.session.call_tool(
                "travel-emission", 
                params
            )
            
            return self._parse_text_content(result)
        except Exception as e:
            logger.error(f"Error in travel emission calculation: {e}")
            return f"Error calculating travel emissions: {e}"
    
    async def calculate_hotel_emission(self, hotel_nights, location, year=None):
        """Calculate carbon emissions from hotel stays"""
        params = {
            "hotel_nights": hotel_nights,
            "location": location
        }
        
        if year:
            params["year"] = year
        
        try:
            logger.debug(f"Hotel emission request: {params}")
            result = await self.session.call_tool(
                "hotel-emission", 
                params
            )
            
            return self._parse_text_content(result)
        except Exception as e:
            logger.error(f"Error in hotel emission calculation: {e}")
            return f"Error calculating hotel emissions: {e}"
    
    async def calculate_travel_spend_emission(self, spend_type, money, money_unit, spend_location, spend_year=None):
        """Calculate carbon emissions from travel-related spending"""
        params = {
            "spend_type": spend_type,
            "money": money,
            "money_unit": money_unit,
            "spend_location": spend_location
        }
        
        if spend_year:
            params["spend_year"] = spend_year
        
        try:
            logger.debug(f"Travel spend emission request: {params}")
            result = await self.session.call_tool(
                "travel-spend", 
                params
            )
            
            return self._parse_text_content(result)
        except Exception as e:
            logger.error(f"Error in travel spend emission calculation: {e}")
            return f"Error calculating travel spend emissions: {e}"
    
    async def search_emission_factors(self, query, category="", region="", year=None, source="", unit_type="", data_version=""):
        """Search for emission factors in the Climatiq database with optional metadata filters"""
        params = {
            "query": query
        }
        
        # Add optional parameters if provided
        if category:
            params["category"] = category
        if region:
            params["region"] = region
        if year:
            params["year"] = year
        if source:
            params["source"] = source
        if unit_type:
            params["unit_type"] = unit_type
        if data_version:
            params["data_version"] = data_version
        
        try:
            logger.debug(f"Search emission factors request: {params}")
            result = await self.session.call_tool(
                "search-emission-factors", 
                params
            )
            
            return self._parse_text_content(result)
        except Exception as e:
            logger.error(f"Error in emission factor search: {e}")
            return f"Error searching emission factors: {e}"
    
    async def calculate_cloud_computing_emission(self, provider, service, region, usage_amount, usage_unit):
        """Calculate carbon emissions from cloud computing"""
        try:
            logger.debug(f"Cloud computing emission request: provider={provider}, service={service}, region={region}")
            result = await self.session.call_tool(
                "cloud-computing-emission", 
                {
                    "provider": provider,
                    "service": service,
                    "region": region,
                    "usage_amount": usage_amount,
                    "usage_unit": usage_unit
                }
            )
            
            return self._parse_text_content(result)
        except Exception as e:
            logger.error(f"Error in cloud computing emission calculation: {e}")
            return f"Error calculating cloud computing emissions: {e}"
    
    async def calculate_freight_emission(self, mode, weight, distance, weight_unit="t", distance_unit="km"):
        """Calculate carbon emissions from freight transportation"""
        try:
            logger.debug(f"Freight emission request: mode={mode}, weight={weight}, distance={distance}")
            result = await self.session.call_tool(
                "freight-emission", 
                {
                    "mode": mode,
                    "weight": weight,
                    "weight_unit": weight_unit,
                    "distance": distance,
                    "distance_unit": distance_unit
                }
            )
            
            return self._parse_text_content(result)
        except Exception as e:
            logger.error(f"Error in freight emission calculation: {e}")
            return f"Error calculating freight emissions: {e}"
    
    async def calculate_procurement_emission(self, amount, category, currency="USD", country="US"):
        """Calculate carbon emissions from procurement spending"""
        try:
            logger.debug(f"Procurement emission request: amount={amount}, category={category}")
            result = await self.session.call_tool(
                "procurement-emission", 
                {
                    "amount": amount,
                    "currency": currency,
                    "country": country,
                    "category": category
                }
            )
            
            return self._parse_text_content(result)
        except Exception as e:
            logger.error(f"Error in procurement emission calculation: {e}")
            return f"Error calculating procurement emissions: {e}"
    
    async def calculate_custom_emission(self, activity_id, value, unit):
        """Calculate emissions using a specific emission factor by activity ID"""
        try:
            logger.debug(f"Custom emission calculation request: activity_id={activity_id}, value={value}, unit={unit}")
            result = await self.session.call_tool(
                "custom-emission-calculation", 
                {
                    "activity_id": activity_id,
                    "value": value,
                    "unit": unit
                }
            )
            
            return self._parse_text_content(result)
        except Exception as e:
            logger.error(f"Error in custom emission calculation: {e}")
            return f"Error calculating custom emissions: {e}"
    
    async def list_resources(self):
        """List all available resources (cached calculation results)"""
        try:
            logger.debug("Listing resources")
            resources = await self.session.list_resources()
            
            # Process resources to handle different object types
            processed_resources = []
            for resource in resources:
                try:
                    # Handle resource objects of different types
                    if hasattr(resource, 'uri'):
                        processed_resources.append(resource)
                    elif isinstance(resource, tuple) and len(resource) >= 2:
                        # Create a simple object with uri attribute
                        class SimpleResource:
                            def __init__(self, uri, name=None):
                                self.uri = uri
                                self.name = name
                        
                        processed_resources.append(SimpleResource(resource[1], resource[0]))
                    else:
                        logger.warning(f"Skipping resource with unknown format: {resource}")
                except Exception as e:
                    logger.error(f"Error processing resource: {e}")
            
            return processed_resources
        except Exception as e:
            logger.error(f"Error listing resources: {e}")
            return []
    
    async def read_resource(self, resource_uri):
        """Read the content of a specific resource"""
        try:
            logger.debug(f"Reading resource: {resource_uri}")
            content, mime_type = await self.session.read_resource(resource_uri)
            
            if mime_type == "application/json":
                try:
                    return json.loads(content)
                except json.JSONDecodeError:
                    return content
            
            return content
        except Exception as e:
            logger.error(f"Error reading resource {resource_uri}: {e}")
            return f"Error reading resource: {e}"
    
    async def get_climate_impact_explanation(self, calculation_id, detail_level="detailed"):
        """Get a natural language explanation of climate impact for a calculation"""
        try:
            logger.debug(f"Climate impact explanation request for calculation_id={calculation_id}")
            result = await self.session.get_prompt(
                "climate-impact-explanation", 
                {
                    "calculation_id": calculation_id,
                    "detail_level": detail_level
                }
            )
            
            if result and result.messages and len(result.messages) > 0:
                return result.messages[0].content.text
            
            return "No explanation available."
        except Exception as e:
            logger.error(f"Error getting climate impact explanation: {e}")
            return f"Error getting climate impact explanation: {e}"

# Example usage of the Climatiq Assistant by an LLM
async def example_llm_interaction():
    """
    This simulates how an LLM like Claude would use the Climatiq Assistant
    to provide carbon emission calculations and climate impact information in a conversation.
    """
    logger.info("=== Climatiq LLM Example Client ===")
    logger.info("Connecting to Climatiq MCP server...")
    
    try:
        async with ClimatiqAssistant() as assistant:
            # Use timeouts for all API calls to avoid hanging
            timeout = 30.0
            
            logger.info("\n=== EXAMPLE 1: ELECTRICITY EMISSIONS ===")
            logger.info("User: 'What is the carbon footprint of using 1000 kWh of electricity in Germany?'")
            
            # Calculate electricity emissions
            try:
                electricity_result = await asyncio.wait_for(
                    assistant.calculate_electricity_emission(
                        energy=1000,
                        energy_unit="kWh",
                        region="DE"
                    ),
                    timeout=timeout
                )
                
                logger.info("\nLLM response (using the data):")
                logger.info(f"According to my calculations, {electricity_result}")
            except asyncio.TimeoutError:
                logger.error("Electricity emission calculation timed out")
            except Exception as e:
                logger.error(f"Error in electricity example: {e}")
            
            # Only include a subset of examples to avoid overwhelming the API
            # and simplify the client for demonstration purposes
            
            logger.info("\n=== EXAMPLE 2: TRAVEL EMISSIONS ===")
            logger.info("User: 'What's the carbon footprint of driving 100 km in a car?'")
            
            try:
                # Use a simple car travel example that we know works
                car_result = await asyncio.wait_for(
                    assistant.calculate_travel_emission(
                        mode="car",
                        distance=100,
                        distance_unit="km"
                    ),
                    timeout=timeout
                )
                
                logger.info("\nLLM response (using the data):")
                logger.info(f"For your car journey: {car_result}")
            except asyncio.TimeoutError:
                logger.error("Car emission calculation timed out")
            except Exception as e:
                logger.error(f"Error in car travel example: {e}")
            
            logger.info("\n=== EXAMPLE 3: SEARCH EMISSION FACTORS ===")
            logger.info("User: 'What emission factors are available for electricity in the US?'")
            
            try:
                # Search for emission factors
                search_result = await asyncio.wait_for(
                    assistant.search_emission_factors(
                        query="electricity",
                        region="US",
                        category="Electricity"
                    ),
                    timeout=timeout
                )
                
                logger.info("\nLLM response (using the data):")
                logger.info(f"I found these emission factors for electricity in the US:\n{search_result}")
            except asyncio.TimeoutError:
                logger.error("Search emission factors timed out")
            except Exception as e:
                logger.error(f"Error in search example: {e}")
            
            # List resources
            try:
                logger.info("\n=== RESOURCES CREATED ===")
                resources = await asyncio.wait_for(
                    assistant.list_resources(),
                    timeout=timeout
                )
                
                logger.info(f"Created {len(resources)} resources during this session")
                
                # Properly display each resource
                for i, resource in enumerate(resources):
                    try:
                        if hasattr(resource, 'uri') and resource.uri:
                            logger.info(f"Resource {i+1}: {resource.uri}")
                        elif isinstance(resource, list):
                            # Handle case where a resource is a list of resources
                            logger.info(f"Resource group {i+1}:")
                            for j, sub_resource in enumerate(resource):
                                if hasattr(sub_resource, 'uri') and sub_resource.uri:
                                    logger.info(f"  - {j+1}: {sub_resource.uri}")
                                else:
                                    logger.info(f"  - {j+1}: {sub_resource}")
                        else:
                            # Try to display as much useful information as possible
                            if hasattr(resource, '__dict__'):
                                # If it's a custom object, show its attributes
                                attrs = vars(resource)
                                if 'uri' in attrs:
                                    logger.info(f"Resource {i+1}: {attrs['uri']}")
                                elif 'name' in attrs and 'uri' in attrs:
                                    logger.info(f"Resource {i+1}: {attrs['name']} ({attrs['uri']})")
                                else:
                                    logger.info(f"Resource {i+1}: {attrs}")
                            else:
                                logger.info(f"Resource {i+1}: {resource}")
                    except Exception as e:
                        logger.error(f"Error displaying resource {i+1}: {e}")
            except Exception as e:
                logger.error(f"Error listing resources: {e}")
            
            logger.info("\nClimatiq Assistant session completed!")
    
    except Exception as e:
        logger.error(f"Error in example LLM interaction: {e}")
    
    logger.info("\nClimatiq LLM example client completed")

if __name__ == "__main__":
    try:
        asyncio.run(example_llm_interaction())
    except KeyboardInterrupt:
        logger.info("Example client interrupted by user")
    except Exception as e:
        logger.exception(f"Unhandled error in main: {e}")
