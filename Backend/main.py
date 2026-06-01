from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from algorithms.get_POI import Get_POI

app = FastAPI()
poi_service = Get_POI()

class POIRequest(BaseModel):
    latitude: float
    longitude: float

@app.post("/api/poi")
async def get_nearby_poi(request: POIRequest):
    data = poi_service.call_API(request.latitude, request.longitude)
    if data is None:
        raise HTTPException(status_code=500, detail="Failed to fetch POI data")
    return data