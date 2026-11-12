import os
import socket
from pathlib import Path
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from dotenv import load_dotenv
import requests
import pandas as pd

load_dotenv()
API_KEY = os.getenv("GOOGLE_MAPS_API_KEY")


def decode_polyline(encoded_polyline):
    """
    Decode a Google encoded polyline into a list of (lat, lng) tuples.
    """
    points = []
    index = 0
    lat = 0
    lng = 0

    while index < len(encoded_polyline):
        shift = 0
        result = 0
        while True:
            byte = ord(encoded_polyline[index]) - 63
            index += 1
            result |= (byte & 0x1F) << shift
            shift += 5
            if byte < 0x20:
                break
        lat += ~(result >> 1) if result & 1 else result >> 1

        shift = 0
        result = 0
        while True:
            byte = ord(encoded_polyline[index]) - 63
            index += 1
            result |= (byte & 0x1F) << shift
            shift += 5
            if byte < 0x20:
                break
        lng += ~(result >> 1) if result & 1 else result >> 1

        points.append((lat / 1e5, lng / 1e5))

    return points


def save_route_map(route_points, user_location, destination_location, output_file):
    """
    Save a simple HTML map that shows the route between two points.
    """
    if not route_points:
        raise ValueError("route_points cannot be empty")

    center_lat = (user_location[0] + destination_location[0]) / 2
    center_lng = (user_location[1] + destination_location[1]) / 2
    route_points_js = ",\n".join(
        f"[{latitude}, {longitude}]" for latitude, longitude in route_points
    )

    html = f"""<!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="utf-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>EV Route Preview</title>
        <link
            rel="stylesheet"
            href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css"
            integrity="sha256-p4NxAoJBhIIN+hmNHrzRCf9tD/miZyoHS5obTRR9BMY="
            crossorigin=""
        >
        <style>
            body {{
                margin: 0;
                font-family: Arial, sans-serif;
            }}
            #map {{
                height: 100vh;
                width: 100%;
            }}
        </style>
    </head>
    <body>
        <div id="map"></div>
        <script
            src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"
            integrity="sha256-20nQCchB9co0qIjJZRGuk2/Z9VM+kNiyxNV1lvTlZBo="
            crossorigin=""
        ></script>
        <script>
            const map = L.map("map").setView([{center_lat}, {center_lng}], 13);

            L.tileLayer("https://tile.openstreetmap.org/{{z}}/{{x}}/{{y}}.png", {{
                maxZoom: 19,
                attribution: "&copy; OpenStreetMap contributors"
            }}).addTo(map);

            const routePoints = [
                {route_points_js}
            ];

            const routeLine = L.polyline(routePoints, {{
                color: "#1d4ed8",
                weight: 5
            }}).addTo(map);

            L.marker([{user_location[0]}, {user_location[1]}]).addTo(map)
                .bindPopup("Origin");

            L.marker([{destination_location[0]}, {destination_location[1]}]).addTo(map)
                .bindPopup("Destination");

            map.fitBounds(routeLine.getBounds(), {{ padding: [30, 30] }});
        </script>
    </body>
    </html>
    """

    output_path = Path(output_file)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(html, encoding="utf-8")
    return output_path.resolve()


def find_free_port():
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


def serve_map_file(map_file_path):
    """
    Start a small local HTTP server so the generated map can be opened by URL.
    """
    map_path = Path(map_file_path).resolve()
    directory = map_path.parent
    port = find_free_port()
    handler = partial(SimpleHTTPRequestHandler, directory=str(directory))
    server = ThreadingHTTPServer(("127.0.0.1", port), handler)
    return server, f"http://127.0.0.1:{port}/{map_path.name}"

def get_distance_ev(destination_location, user_location):
    '''
    Inputs are tuple
    '''
    BASE_URL = "https://routes.googleapis.com/directions/v2:computeRoutes"
    dest_lat, dest_lng = destination_location
    user_lat, user_lng = user_location
    headers = {
        "Content-Type": "application/json",
        "X-Goog-Api-Key": API_KEY,
        "X-Goog-FieldMask": "routes.distanceMeters,routes.duration,routes.polyline.encodedPolyline"
    }
    
    payload = {
        "origin": {
            "location": {
                "latLng": {
                    "latitude": user_lat,
                    "longitude": user_lng
                }
            }
        },
        "destination": {
            "location": {
                "latLng": {
                    "latitude": dest_lat,
                    "longitude": dest_lng
                }
            }
        },
        "travelMode": "DRIVE",
        "routingPreference": "TRAFFIC_AWARE",
        "computeAlternativeRoutes": False,
        "units": "METRIC"
    }
    
    response = requests.post(BASE_URL, json=payload, headers=headers)

    if response.status_code == 200:
        results = response.json()
        # The distance is returned in meters
        distance_meters = results['routes'][0]['distanceMeters']
        print(f"Distance: {distance_meters} meters")
        # print(results)
        return results
    else:
        print(f"Error: {response.status_code}")
        print(response.text)
        return None


def main():
    # Example coordinates in dataset.
    
    MOCK_DATASET = r"data\taiwan_ev_station_mock.csv"
    EV_station_dataset = pd.read_csv(MOCK_DATASET)

    user_location = tuple(EV_station_dataset.loc[0, ['latitude', 'longitude']])
    destination_location = tuple(EV_station_dataset.loc[1, ['latitude', 'longitude']])

    results = get_distance_ev(destination_location, user_location)
    if not results or not results.get("routes"):
        print("Could not get a route from the Routes API.")
        return

    encoded_polyline = results["routes"][0]["polyline"]["encodedPolyline"]
    route_points = decode_polyline(encoded_polyline)
    output_path = save_route_map(
        route_points=route_points,
        user_location=user_location,
        destination_location=destination_location,
        output_file="data/route_map.html"
    )

    print(f"Map saved to: {output_path}")
    server, map_url = serve_map_file(output_path)
    print(f"Map URL: {map_url}")
    print("Keep this program running, then Ctrl+Click the URL above to open the map.")

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nStopping local map server...")
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
