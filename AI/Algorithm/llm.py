import os
from google import genai
from google.genai import types


API_KEY = os.getenv("GEMINI_API_KEY", "")

def generate_ev_explanation(station_data):
    # Initialize the client. It automatically looks for the GEMINI_API_KEY environment variable.
    client = genai.Client()
    
    # Define system instructions to give the model its persona and rules
    system_instruction = (
        "You are a helpful EV charging assistant. Your goal is to look at the data "
        "of a highly recommended EV station "
        "to the driver justifying why they should pick it compared to other choices. Focus on great trade-offs "
        "(distance, price, POI, waiting time). Treat the user as if they only know basic words, don't use big words. Be concise and to the point. Always highlight the most important reason first."
    )
    
    # Combine the system instruction and user data into a generation config
    config = types.GenerateContentConfig(
        system_instruction=system_instruction,
        temperature=0.3 # Low temperature keeps it factual and focused on your data
    )
    
    # Construct the user prompt with your station data
    user_prompt = f"Station Data: {station_data}\n\nExplain why the driver should choose this station:"

    # Call the free Gemini 3.5 Flash model
    response = client.models.generate_content(
        model='gemini-3.5-flash',
        contents=user_prompt,
        config=config
    )
    
    return response.text