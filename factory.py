from tools.itinerary_tool import create_itinerary_tool
from tools.maps_tool import create_maps_tool
from tools.rag_tool import create_rag_tool
from tools.weather_tool import create_weather_tool
from tools.web_search_tool import create_web_search_tool


def create_travel_tools():
    return [
        create_rag_tool(),
        create_weather_tool(),
        create_maps_tool(),
        create_web_search_tool(),
        create_itinerary_tool(),
    ]
