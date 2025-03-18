import json
import logging
import mcp.types as types
import httpx

# Set up logger
logger = logging.getLogger(__name__)

async def set_api_key_tool(config, arguments, server, climatiq_request):
    """
    Set the Climatiq API key for authentication with the API.
    
    This tool configures the Climatiq API key used for all subsequent API calls.
    The key is stored in memory for the duration of the server session.
    """
    api_key = arguments.get("api_key")
    
    if not api_key:
        raise ValueError("API key is required")
    
    # Validate API key by making a test request
    test_headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json"
    }
    
    try:
        # Use httpx directly as we can't use climatiq_request yet
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.get(f"{config['base_url']}/data/v1/search", 
                                        params={"query": "electricity", "data_version": config["data_version"]},
                                        headers=test_headers)
            
            if response.status_code != 200:
                error_detail = "Invalid API key or API connection issue"
                try:
                    error_json = response.json()
                    if "error" in error_json:
                        error_detail = error_json["error"]
                    elif "message" in error_json:
                        error_detail = error_json["message"]
                except:
                    pass
                    
                raise ValueError(f"API key validation failed: {error_detail}")
        
        # If we get here, the API key is valid
        config["api_key"] = api_key
        return "Climatiq API key configured successfully. You can now use other tools to calculate emissions."
        
    except httpx.RequestError as e:
        raise ValueError(f"Failed to connect to Climatiq API: {str(e)}")
    except Exception as e:
        raise ValueError(f"Error validating API key: {str(e)}")

async def electricity_emission_tool(config, arguments, server, climatiq_request):
    """
    Calculate carbon emissions from electricity consumption.
    
    This tool calculates the greenhouse gas emissions associated with electricity usage based on:
    - The amount of energy consumed (in kWh, MWh, etc.)
    - The region/country where the electricity is consumed (affecting the grid mix)
    
    It uses Climatiq's electricity emission factors which account for the specific energy 
    generation mix of the specified region, providing accurate CO2e estimations.
    """
    energy = arguments.get("energy")
    energy_unit = arguments.get("energy_unit")
    region = arguments.get("region", "US")
    
    if not energy or not energy_unit:
        raise ValueError("Missing required parameters for electricity emission calculation")
        
    # Construct the request to the Climatiq API
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
        result = await climatiq_request("/data/v1/estimate", request_data)
        
        # Store in cache
        cache_id = f"electricity_{energy}_{energy_unit}_{region}_{id(result)}"
        
        co2e = result.get("co2e", 0)
        co2e_unit = result.get("co2e_unit", "kg")
        result_text = f"Electricity consumption of {energy} {energy_unit} in {region} results in {co2e} {co2e_unit} of CO2e emissions."
        
        if "emission_factor" in result and result["emission_factor"].get("name"):
            ef_name = result["emission_factor"]["name"]
            result_text += f"\nEmission factor used: {ef_name}"
        
        result_text += f"\n\nDetailed results are available as a resource with ID: {cache_id}"
        
        return result_text, result, cache_id
    except Exception as e:
        error_msg = f"Error calculating electricity emissions: {str(e)}"
        raise ValueError(error_msg)

async def travel_emission_tool(config, arguments, server, climatiq_request):
    """
    Calculate carbon emissions from passenger travel.
    
    This tool estimates the greenhouse gas emissions for various modes of passenger transportation:
    - Car travel (with options for vehicle size, fuel type, and passenger count)
    - Air travel (with options for flight length categories)
    - Train travel (with options for train types)
    
    It supports both direct distance input and origin-destination location lookup for 
    automatic distance calculation. The emissions calculation accounts for the specific 
    transportation mode characteristics and regional factors.
    """
    mode = arguments.get("mode")
    if not mode:
        raise ValueError("Missing travel mode (car, plane, train)")

    # Check if we need to use the distance API or the direct calculation
    if (arguments.get("origin") and arguments.get("destination")) or mode.lower() == "flight":
        try:
            return await _travel_distance_api(config, arguments, climatiq_request)
        except Exception as e:
            raise ValueError(f"Error calculating travel emissions with locations: {str(e)}")
    else:
        try:
            return await _travel_estimate_api(config, arguments, climatiq_request)
        except Exception as e:
            raise ValueError(f"Error calculating travel emissions with distance: {str(e)}")
            
async def _travel_distance_api(config, arguments, climatiq_request):
    """Helper function to calculate travel emissions using the distance API with origin/destination."""
    mode = arguments.get("mode").lower()
    origin = arguments.get("origin")
    destination = arguments.get("destination")
    
    # Check for flight-specific parameters
    if mode == "flight" or mode == "plane":
        # Get flight-specific parameters
        flight_type = arguments.get("vehicle_type", "international")
        passengers = arguments.get("passengers", 1)
        cabin_class = arguments.get("cabin_class", "economy")
        
        # For flights with specific origin/destination
        if origin and destination:
            request_data = {
                "legs": [
                    {
                        "from": origin,
                        "to": destination,
                        "passengers": passengers,
                        "cabin_class": cabin_class
                    }
                ]
            }
            
            result = await climatiq_request("/travel/flights", request_data)
            
            # Format the result
            co2e = result.get("co2e", 0)
            co2e_unit = result.get("co2e_unit", "kg")
            distance = result.get("distance_value", 0)
            distance_unit = result.get("distance_unit", "km")
            
            origin_text = origin.get("query") if isinstance(origin, dict) else origin
            destination_text = destination.get("query") if isinstance(destination, dict) else destination
            
            result_text = f"Flight from {origin_text} to {destination_text} "
            result_text += f"({distance} {distance_unit}) with {passengers} passenger(s) in {cabin_class} class "
            result_text += f"results in {co2e} {co2e_unit} of CO2e emissions."
            
            # Store in cache
            cache_id = f"flight_{origin_text}_{destination_text}_{cabin_class}_{id(result)}"
            
            return result_text, result, cache_id
    
    # For other modes (car, train) with origin/destination
    if not origin or not destination:
        raise ValueError("Origin and destination are required for travel distance calculation")

    # Prepare car/train specific details
    vehicle_details = {}
    
    if mode == "car":
        car_details = arguments.get("car_details", {})
        vehicle_type = car_details.get("car_type", arguments.get("vehicle_type", "medium"))
        fuel_type = car_details.get("fuel_type", arguments.get("fuel_type", "regular"))
        engine_size = car_details.get("engine_size")
        
        vehicle_details = {
            "vehicle_type": vehicle_type,
            "fuel_type": fuel_type
        }
        
        if engine_size:
            vehicle_details["engine_size"] = engine_size
    
    elif mode == "train":
        train_type = arguments.get("vehicle_type", "national_rail")
        vehicle_details = {"train_type": train_type}
    
    # Construct the request
    request_data = {
        "origin": origin,
        "destination": destination,
        "transport_method": mode,
    }
    
    # Add vehicle specific details if any
    if vehicle_details:
        request_data.update(vehicle_details)
    
    result = await climatiq_request("/travel/distance", request_data)
    
    # Format the result
    co2e = result.get("co2e", 0)
    co2e_unit = result.get("co2e_unit", "kg")
    distance = result.get("distance", {}).get("value", 0)
    distance_unit = result.get("distance", {}).get("unit", "km")
    
    origin_text = origin.get("query") if isinstance(origin, dict) else origin
    destination_text = destination.get("query") if isinstance(destination, dict) else destination
    
    result_text = f"{mode.capitalize()} travel from {origin_text} to {destination_text} "
    result_text += f"({distance} {distance_unit}) results in {co2e} {co2e_unit} of CO2e emissions."
    
    # Store in cache
    cache_id = f"{mode}_{origin_text}_{destination_text}_{id(result)}"
    
    return result_text, result, cache_id

async def _travel_estimate_api(config, arguments, climatiq_request):
    """Helper function to calculate travel emissions using direct distance input."""
    mode = arguments.get("mode").lower()
    distance = arguments.get("distance")
    distance_unit = arguments.get("distance_unit", "km")
    
    if not distance:
        raise ValueError(f"Missing distance for {mode} travel")
    
    # Construct the request based on mode
    activity_mapping = {
        "car": "passenger_vehicle-vehicle_type_car-fuel_source_na-engine_size_na-vehicle_age_na-vehicle_weight_na",
        "plane": "passenger_flight-route_type_international-aircraft_type_na-distance_na-class_na-rf_included",
        "train": "passenger_train-route_type_commuter_rail-fuel_source_na"
    }
    
    # Simpler implementation that matches the example in the notebook
    # and ensures compatibility with the API
    request_data = {
        "emission_factor": {
            "activity_id": activity_mapping.get(mode, activity_mapping["car"]),
            "data_version": config["data_version"]
        },
        "parameters": {
            "distance": distance,
            "distance_unit": distance_unit
        }
    }
    
    # Add region if provided
    region = arguments.get("region")
    if region:
        request_data["emission_factor"]["region"] = region
        
    # We no longer add these parameters to avoid API errors
    # Instead of trying to use complex parameters, keep it simple
    
    try:
        result = await climatiq_request("/data/v1/estimate", request_data)
        
        # Store in cache
        cache_id = f"travel_{mode}_{distance}_{distance_unit}_{id(result)}"
        
        co2e = result.get("co2e", 0)
        co2e_unit = result.get("co2e_unit", "kg")
        
        result_text = f"{mode.capitalize()} travel of {distance} {distance_unit} "
        if region:
            result_text += f"in {region} "
        result_text += f"results in {co2e} {co2e_unit} of CO2e emissions."
        
        if "emission_factor" in result and result["emission_factor"].get("name"):
            ef_name = result["emission_factor"]["name"]
            result_text += f"\nEmission factor used: {ef_name}"
        
        result_text += f"\n\nDetailed results are available as a resource with ID: {cache_id}"
        
        return result_text, result, cache_id
    except Exception as e:
        logger.error(f"Error in travel estimation: {str(e)}")
        raise ValueError(f"Error calculating travel emissions: {str(e)}")

async def search_emission_factors_tool(config, arguments, server, climatiq_request):
    """
    Search for emission factors in the Climatiq database.
    
    This tool allows users to search through Climatiq's extensive database of emission factors
    using keywords and filters. It helps users find the appropriate emission factors for 
    specific activities, regions, or categories. The search results include:
    - The name of the emission factor
    - Activity ID (used for custom calculations)
    - Region specificity
    - Year of publication
    - Category classification
    - Source organization
    - Available units
    
    This tool is especially useful before performing custom calculations, as it helps 
    identify the correct activity_id to use.
    """
    query = arguments.get("query")
    category = arguments.get("category", "")
    region = arguments.get("region", "")
    year = arguments.get("year", "")
    source = arguments.get("source", "")
    data_version = arguments.get("data_version", config["data_version"])
    unit_type = arguments.get("unit_type", "")
    
    if not query:
        raise ValueError("Missing search query")
        
    # Construct the request to the Climatiq API
    params = {
        "query": query,
        "data_version": data_version
    }
    
    # Add all optional filters if provided
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
    
    try:    
        result = await climatiq_request("/data/v1/search", params, method="GET")
        
        # Process search results
        results = result.get("results", [])
        total_count = len(results)
        
        if total_count == 0:
            result_text = "No emission factors found matching your search criteria."
            return result_text, {}, None
            
        # Format a summary of the results
        result_text = f"Found {total_count} emission factors matching '{query}'.\n\n"
        
        # Display the first 5 results (or fewer if less are available)
        max_display = min(5, total_count)
        result_text += f"Here are the first {max_display} results:\n\n"
        
        for i in range(max_display):
            ef = results[i]
            result_text += f"{i+1}. {ef.get('name', 'Unnamed factor')}\n"
            result_text += f"   Activity ID: {ef.get('activity_id', 'N/A')}\n"
            result_text += f"   Region: {ef.get('region_name', ef.get('region', 'N/A'))}\n"
            result_text += f"   Year: {ef.get('year', 'N/A')}\n"
            result_text += f"   Source: {ef.get('source', 'N/A')}\n"
            if ef.get('unit'):
                result_text += f"   Unit: {ef.get('unit', 'N/A')}\n"
            result_text += "\n"
        
        # If there are more results than we displayed
        if total_count > max_display:
            result_text += f"\n... and {total_count - max_display} more results."
            
        # Include a note about using these factors with the custom calculation tool
        result_text += "\n\nTo use one of these emission factors, copy its Activity ID and use it with the custom-emission-calculation tool."
        
        # Cache the search results
        cache_id = f"search_{query.replace(' ', '_')}_{id(result)}"
        
        return result_text, result, cache_id
    except Exception as e:
        error_msg = f"Error searching emission factors: {str(e)}"
        raise ValueError(error_msg)

async def custom_emission_calculation_tool(config, arguments, server, climatiq_request):
    """
    Calculate emissions using a specific emission factor by activity ID.
    
    This advanced tool allows for precise carbon calculations using any emission factor 
    available in the Climatiq database. Users need to specify:
    - The exact activity_id (which can be found using the search-emission-factors tool)
    - The value of the activity (e.g., amount consumed, distance traveled)
    - The unit of measurement (e.g., kWh, km, kg)
    
    This tool is highly flexible and can be used for any emission calculation supported
    by Climatiq when you know the specific emission factor you need to use.
    """
    activity_id = arguments.get("activity_id")
    value = arguments.get("value")
    unit = arguments.get("unit")
    
    if not activity_id or value is None or not unit:
        raise ValueError("Missing required parameters for custom emission calculation")
        
    # Construct the request to the Climatiq API
    request_data = {
        "emission_factor": {
            "activity_id": activity_id,
            "data_version": config["data_version"]
        },
        "parameters": {
            unit: value
        }
    }
    
    try:
        result = await climatiq_request("/data/v1/estimate", request_data)
        
        # Store in cache
        cache_id = f"custom_{activity_id}_{value}_{unit}_{id(result)}"
        
        co2e = result.get("co2e", 0)
        co2e_unit = result.get("co2e_unit", "kg")
        factor_name = result.get("emission_factor", {}).get("name", "Custom factor")
        
        result_text = f"Custom calculation using '{factor_name}' activity:\n"
        result_text += f"{value} {unit} results in {co2e} {co2e_unit} of CO2e emissions."
        
        if "emission_factor" in result:
            ef = result["emission_factor"]
            result_text += f"\n\nFactor details:"
            result_text += f"\nName: {ef.get('name', 'N/A')}"
            result_text += f"\nRegion: {ef.get('region', 'Global')}"
            result_text += f"\nSource: {ef.get('source', 'Unknown')}"
        
        result_text += f"\n\nDetailed results are available as a resource with ID: {cache_id}"
        
        return result_text, result, cache_id
    except Exception as e:
        error_msg = f"Error in custom emission calculation: {str(e)}"
        raise ValueError(error_msg)

async def cloud_computing_emission_tool(config, arguments, server, climatiq_request):
    """
    Calculate carbon emissions from cloud computing resource usage.
    
    This specialized tool estimates the carbon footprint of cloud computing services across
    major providers (AWS, Azure, GCP). It accounts for:
    - The specific cloud provider (affects emission factors)
    - The type of service used (compute, storage, networking, etc.)
    - The region/data center location (significant regional variations in grid emissions)
    - Usage amount and units (CPU hours, GB-months, etc.)
    
    This tool helps organizations understand and measure the environmental impact of 
    their cloud infrastructure and can support sustainable cloud deployment decisions.
    """
    provider = arguments.get("provider")
    service = arguments.get("service")
    region = arguments.get("region")
    usage_amount = arguments.get("usage_amount")
    usage_unit = arguments.get("usage_unit")
    
    if not provider or not service or not region or not usage_amount or not usage_unit:
        raise ValueError("Missing required parameters for cloud computing emission calculation")
        
    # Construct the request to the Climatiq API
    request_data = {
        "emission_factor": {
            "activity_id": f"cloud_computing-{provider}-{service}-{region}",
            "data_version": config["data_version"]
        },
        "parameters": {
            usage_unit: usage_amount
        }
    }
    
    try:
        result = await climatiq_request("/data/v1/estimate", request_data)
        
        # Store in cache
        cache_id = f"cloud_{provider}_{service}_{region}_{usage_amount}_{usage_unit}_{id(result)}"
        
        co2e = result.get("co2e", 0)
        co2e_unit = result.get("co2e_unit", "kg")
        
        result_text = f"Cloud computing usage of {usage_amount} {usage_unit} with {provider} {service} in {region} "
        result_text += f"results in {co2e} {co2e_unit} of CO2e emissions."
        result_text += f"\n\nDetailed results are available as a resource with ID: {cache_id}"
        
        return result_text, result, cache_id
        
    except ValueError as e:
        if "API request failed" in str(e):
            error_text = f"Error calculating emissions: {str(e)}\n\n"
            error_text += "This might be due to an unsupported provider/service/region combination. "
            error_text += "Try searching for the correct emission factor first using the search-emission-factors tool with a query like 'cloud_computing'."
            return error_text, None, None
        else:
            raise

async def freight_emission_tool(config, arguments, server, climatiq_request):
    """
    Calculate carbon emissions from freight transportation.
    
    This tool estimates greenhouse gas emissions from moving goods via different freight modes:
    - Truck/road freight
    - Rail freight
    - Sea/shipping freight
    - Air freight
    
    The calculation considers:
    - The weight of goods being transported
    - The distance traveled
    - The specific transport mode
    
    It's especially useful for logistics companies, supply chain operations, and 
    organizations looking to understand and reduce their shipping-related carbon footprint.
    """
    mode = arguments.get("mode")
    weight = arguments.get("weight")
    weight_unit = arguments.get("weight_unit", "t")
    distance = arguments.get("distance")
    distance_unit = arguments.get("distance_unit", "km")
    
    if not mode or not weight or not distance:
        raise ValueError("Missing required parameters for freight emission calculation")
        
    # Different activity IDs based on freight mode
    activity_id = ""
    
    if mode.lower() == "truck" or mode.lower() == "road":
        activity_id = "freight_vehicle-vehicle_type_truck-fuel_source_na-vehicle_weight_na-vehicle_age_na"
    elif mode.lower() == "rail":
        activity_id = "freight_train-route_type_na-fuel_source_na"
    elif mode.lower() in ["ship", "sea", "marine"]:
        activity_id = "sea_freight-vessel_type_na-route_type_na-fuel_source_na"
    elif mode.lower() in ["air", "plane", "aircraft"]:
        activity_id = "air_freight-route_type_na-distance_na"
    else:
        raise ValueError(f"Unsupported freight mode: {mode}")
        
    # Construct the request to the Climatiq API
    request_data = {
        "emission_factor": {
            "activity_id": activity_id,
            "data_version": config["data_version"]
        },
        "parameters": {
            "weight": weight,
            "weight_unit": weight_unit,
            "distance": distance,
            "distance_unit": distance_unit
        }
    }
    
    result = await climatiq_request("/data/v1/estimate", request_data)
    
    # Store in cache
    cache_id = f"freight_{mode}_{weight}_{weight_unit}_{distance}_{distance_unit}_{id(result)}"
    
    co2e = result.get("co2e", 0)
    co2e_unit = result.get("co2e_unit", "kg")
    
    mode_display = mode.capitalize()
    result_text = f"{mode_display} freight of {weight} {weight_unit} over {distance} {distance_unit} "
    result_text += f"results in {co2e} {co2e_unit} of CO2e emissions."
    result_text += f"\n\nDetailed results are available as a resource with ID: {cache_id}"
    
    return result_text, result, cache_id

async def procurement_emission_tool(config, arguments, server, climatiq_request):
    """
    Calculate carbon emissions from procurement and spending.
    
    This tool estimates the greenhouse gas emissions associated with purchasing goods 
    and services (Scope 3, Category 1 emissions). It uses an Economic Input-Output 
    Life Cycle Assessment (EIO-LCA) approach, where emissions are estimated based on:
    - The amount of money spent
    - The spending category (e.g., electronics, food, construction)
    - The currency used
    - The country where purchases are made
    
    This method is especially useful for calculating Scope 3.1 emissions when detailed 
    activity data is not available, providing a practical way to estimate the carbon 
    footprint of an organization's supply chain.
    """
    amount = arguments.get("amount")
    currency = arguments.get("currency", "USD")
    country = arguments.get("country", "US")
    category = arguments.get("category", "")
    
    if not amount or not category:
        raise ValueError("Missing required parameters for procurement emission calculation")
        
    # Construct the request to the Climatiq API
    request_data = {
        "emission_factor": {
            "activity_id": f"purchase_{category}",
            "region": country,
            "data_version": config["data_version"]
        },
        "parameters": {
            "money": amount,
            "money_unit": currency
        }
    }
    
    try:
        result = await climatiq_request("/data/v1/estimate", request_data)
        
        # Store in cache
        cache_id = f"procurement_{category}_{amount}_{currency}_{country}_{id(result)}"
        
        co2e = result.get("co2e", 0)
        co2e_unit = result.get("co2e_unit", "kg")
        
        result_text = f"Procurement spending of {amount} {currency} on {category} in {country} "
        result_text += f"results in {co2e} {co2e_unit} of CO2e emissions."
        result_text += f"\n\nDetailed results are available as a resource with ID: {cache_id}"
        
        return result_text, result, cache_id
        
    except ValueError as e:
        if "API request failed" in str(e):
            error_text = f"Error calculating emissions: {str(e)}\n\n"
            error_text += "This might be due to an unsupported category or country. "
            error_text += "Try searching for the correct emission factor first with a query like 'purchase'."
            return error_text, None, None
        else:
            raise

async def hotel_emission_tool(config, arguments, server, climatiq_request):
    """
    Calculate carbon emissions from hotel stays.
    
    This tool estimates the greenhouse gas emissions associated with hotel accommodations
    based on the number of nights stayed and the location of the hotel. It provides
    valuable data for calculating business travel emissions.
    """
    hotel_nights = arguments.get("hotel_nights")
    location = arguments.get("location")
    year = arguments.get("year")
    
    if not hotel_nights or not location:
        raise ValueError("Missing required parameters for hotel emission calculation")
        
    # Construct the request to the Climatiq API
    request_data = {
        "hotel_nights": hotel_nights,
        "location": location
    }
    
    if year:
        request_data["year"] = year
        
    try:
        result = await climatiq_request("/travel/v1-preview1/hotel", request_data)
        
        # Store in cache
        cache_id = f"hotel_{hotel_nights}_{id(result)}"
        
        co2e = result.get("co2e", 0)
        co2e_unit = result.get("co2e_unit", "kg")
        location_name = result.get("location", {}).get("name", "unknown location")
        
        result_text = f"Hotel stay for {hotel_nights} nights in {location_name} "
        result_text += f"results in {co2e} {co2e_unit} of CO2e emissions."
        result_text += f"\n\nDetailed results are available as a resource with ID: {cache_id}"
        
        return result_text, result, cache_id
        
    except ValueError as e:
        error_text = f"Error calculating hotel emissions: {str(e)}"
        return error_text, None, None

async def travel_spend_tool(config, arguments, server, climatiq_request):
    """
    Calculate carbon emissions from travel-related spending.
    
    This tool uses a spend-based method to estimate emissions from various travel activities:
    - Air travel spending
    - Road travel spending (including taxis)
    - Rail travel spending
    - Sea travel spending
    - Hotel accommodation spending
    
    The calculation uses economic input-output models to estimate the carbon intensity
    of different travel services based on financial spend data.
    """
    spend_type = arguments.get("spend_type")
    money = arguments.get("money")
    money_unit = arguments.get("money_unit")
    spend_location = arguments.get("spend_location")
    spend_year = arguments.get("spend_year")
    
    if not spend_type or not money or not money_unit or not spend_location:
        raise ValueError("Missing required parameters for travel spend calculation")
        
    # Validate spend type
    valid_spend_types = ["air", "road", "rail", "sea", "hotel"]
    if spend_type.lower() not in valid_spend_types:
        raise ValueError(f"Invalid spend_type: {spend_type}. Must be one of: {', '.join(valid_spend_types)}")
        
    # Construct the request to the Climatiq API
    request_data = {
        "spend_type": spend_type.lower(),
        "money": money,
        "money_unit": money_unit,
        "spend_location": spend_location
    }
    
    if spend_year:
        request_data["spend_year"] = spend_year
        
    try:
        result = await climatiq_request("/travel/v1-preview1/spend", request_data)
        
        # Store in cache
        cache_id = f"travel_spend_{spend_type}_{money}_{money_unit}_{id(result)}"
        
        co2e = result.get("co2e", 0)
        co2e_unit = result.get("co2e_unit", "kg")
        location_name = result.get("spend_location", {}).get("name", "unknown location")
        
        spend_type_display = spend_type.capitalize()
        result_text = f"{spend_type_display} travel spending of {money} {money_unit} in {location_name} "
        result_text += f"results in {co2e} {co2e_unit} of CO2e emissions."
        result_text += f"\n\nDetailed results are available as a resource with ID: {cache_id}"
        
        return result_text, result, cache_id
        
    except ValueError as e:
        error_text = f"Error calculating travel spend emissions: {str(e)}"
        return error_text, None, None

def get_tool_definitions():
    """Return the list of tool definitions for the MCP server."""
    return [
        types.Tool(
            name="set-api-key",
            description="Set the Climatiq API key for authentication. This allows the server to make authorized requests to the Climatiq API.",
            inputSchema={
                "type": "object",
                "properties": {
                    "api_key": {"type": "string", "description": "Your Climatiq API key obtained from app.climatiq.io"},
                },
                "required": ["api_key"],
            },
        ),
        types.Tool(
            name="electricity-emission",
            description="Calculate carbon emissions from electricity consumption based on energy amount and regional grid mix.",
            inputSchema={
                "type": "object",
                "properties": {
                    "energy": {"type": "number", "description": "Amount of energy consumed"},
                    "energy_unit": {"type": "string", "description": "Energy unit (kWh, MWh, etc.)"},
                    "region": {"type": "string", "description": "Region code (e.g., US, GB, FR) representing the electricity grid location", "default": "US"},
                },
                "required": ["energy", "energy_unit"],
            },
        ),
        types.Tool(
            name="travel-emission",
            description="Calculate emissions from passenger travel via car, plane, or train, with options for vehicle types and passenger count.",
            inputSchema={
                "type": "object",
                "properties": {
                    "mode": {"type": "string", "description": "Travel mode (car, plane, train)"},
                    "distance": {"type": "number", "description": "Distance traveled (optional if origin and destination are provided)"},
                    "distance_unit": {"type": "string", "description": "Distance unit (km, mi)", "default": "km"},
                    "passengers": {"type": "integer", "description": "Number of passengers (for car travel)", "default": 1},
                    "vehicle_type": {"type": "string", "description": "For car: small/medium/large; For plane: short/medium/long-haul/domestic/international; For train: electric/diesel", "default": "medium"},
                    "fuel_type": {"type": "string", "description": "For car: regular/electric/hybrid", "default": "regular"},
                    "origin": {"type": "object", "description": "Origin location for travel API (allows automatic distance calculation)"},
                    "destination": {"type": "object", "description": "Destination location for travel API (allows automatic distance calculation)"},
                    "year": {"type": "integer", "description": "Year of travel for more accurate emission factors", "default": 2022},
                    "car_details": {"type": "object", "description": "Detailed car specifications for more accurate calculations"},
                    "air_details": {"type": "object", "description": "Detailed flight specifications for more accurate calculations"}
                },
                "required": ["mode"],
            },
        ),
        types.Tool(
            name="search-emission-factors",
            description="Search Climatiq's database for emission factors by keyword, category, region, year, source, and other metadata to find appropriate factors for calculations.",
            inputSchema={
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "Search query for emission factors (e.g., 'electricity', 'flight', 'truck')"},
                    "category": {"type": "string", "description": "Category of emission factors (e.g., 'Energy', 'Transport')", "default": ""},
                    "region": {"type": "string", "description": "Region code to filter results (e.g., 'US', 'EU')", "default": ""},
                    "year": {"type": "integer", "description": "Year of emission factors", "default": 2022},
                    "source": {"type": "string", "description": "Source organization of emission factors (e.g., 'IPCC', 'EPA', 'BEIS')", "default": ""},
                    "data_version": {"type": "string", "description": "Data version of emission factors", "default": ""},
                    "unit_type": {"type": "string", "description": "Unit type of emission factors (e.g., 'energy', 'distance', 'weight')", "default": ""}
                },
                "required": ["query"],
            },
        ),
        types.Tool(
            name="custom-emission-calculation",
            description="Calculate emissions using any specific emission factor identified by its activity_id, allowing for precise and flexible carbon calculations.",
            inputSchema={
                "type": "object",
                "properties": {
                    "activity_id": {"type": "string", "description": "Emission factor activity ID (found via search-emission-factors)"},
                    "value": {"type": "number", "description": "Activity value (amount of the activity)"},
                    "unit": {"type": "string", "description": "Activity unit (e.g., kWh, km, kg, etc.)"},
                },
                "required": ["activity_id", "value", "unit"],
            },
        ),
        types.Tool(
            name="cloud-computing-emission",
            description="Calculate emissions from cloud computing services by provider, service type, and region to assess digital carbon footprint.",
            inputSchema={
                "type": "object",
                "properties": {
                    "provider": {"type": "string", "description": "Cloud provider (aws, azure, gcp)"},
                    "service": {"type": "string", "description": "Cloud service (e.g., compute, storage, database)"},
                    "region": {"type": "string", "description": "Cloud region (e.g., us-east-1, europe-west1)"},
                    "usage_amount": {"type": "number", "description": "Amount of cloud resources used"},
                    "usage_unit": {"type": "string", "description": "Unit for cloud resource (e.g., kWh, GB-hours, CPU-hours)"},
                },
                "required": ["provider", "service", "region", "usage_amount", "usage_unit"],
            },
        ),
        types.Tool(
            name="freight-emission",
            description="Calculate emissions from freight transportation across different modes (truck, rail, ship, air) based on weight and distance.",
            inputSchema={
                "type": "object",
                "properties": {
                    "mode": {"type": "string", "description": "Freight mode (truck, rail, ship, air)"},
                    "weight": {"type": "number", "description": "Weight of goods transported"},
                    "weight_unit": {"type": "string", "description": "Weight unit (t, kg)", "default": "t"},
                    "distance": {"type": "number", "description": "Distance transported"},
                    "distance_unit": {"type": "string", "description": "Distance unit (km, mi)", "default": "km"},
                },
                "required": ["mode", "weight", "distance"],
            },
        ),
        types.Tool(
            name="procurement-emission",
            description="Calculate Scope 3.1 emissions from procurement spending using economic input-output life cycle assessment methods.",
            inputSchema={
                "type": "object",
                "properties": {
                    "amount": {"type": "number", "description": "Amount of money spent"},
                    "currency": {"type": "string", "description": "Currency code (e.g., USD, EUR, GBP)", "default": "USD"},
                    "country": {"type": "string", "description": "Country code where purchases were made", "default": "US"},
                    "category": {"type": "string", "description": "Procurement category (e.g., electronics, food, construction)"},
                },
                "required": ["amount", "category"],
            },
        ),
        types.Tool(
            name="hotel-emission",
            description="Calculate carbon emissions from hotel stays based on the number of nights stayed and the location of the hotel.",
            inputSchema={
                "type": "object",
                "properties": {
                    "hotel_nights": {"type": "number", "description": "Number of nights stayed"},
                    "location": {"type": "string", "description": "Location of the hotel"},
                    "year": {"type": "number", "description": "Year of the hotel stay"},
                },
                "required": ["hotel_nights", "location"],
            },
        ),
        types.Tool(
            name="travel-spend",
            description="Calculate carbon emissions from travel-related spending based on spend type, amount, currency, location, and year.",
            inputSchema={
                "type": "object",
                "properties": {
                    "spend_type": {"type": "string", "description": "Type of travel spending (air, road, rail, sea, hotel)"},
                    "money": {"type": "number", "description": "Amount of money spent"},
                    "money_unit": {"type": "string", "description": "Currency unit for the spent money"},
                    "spend_location": {"type": "string", "description": "Location of the travel spending"},
                    "spend_year": {"type": "number", "description": "Year of the travel spending"},
                },
                "required": ["spend_type", "money", "money_unit", "spend_location"],
            },
        )
    ] 