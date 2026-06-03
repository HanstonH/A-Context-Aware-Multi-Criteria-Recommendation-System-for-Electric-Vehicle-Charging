import { NextResponse } from 'next/server';

export async function POST(request: Request) {
  try {
    const { lat, lng } = await request.json();

    const response = await fetch(`https://places.googleapis.com/v1/places:searchNearby?key=${process.env.GOOGLE_MAPS_API_KEY}`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "X-Goog-FieldMask": "places.displayName,places.formattedAddress,places.location,places.types"
      },
      body: JSON.stringify({
        includedTypes: ["coffee_shop", "restaurant", "shopping_mall", "park"],
        locationRestriction: {
          circle: {
            center: { latitude: lat, longitude: lng },
            radius: 500.0
          }
        }
      })
    });

    const data = await response.json();
    return NextResponse.json(data);
  } catch (error) {
    return NextResponse.json({ error: "Failed to fetch POIs" }, { status: 500 });
  }
}