const axios = require('axios')
const FASTAPI_URL = process.env.FASTAPI_URL || 'http://localhost:8000'
// POIs around a station, for display on the map only (not part of the ranking).
const getPois = async (req, res) => {
  const lat = Number(req.query.lat)
  const lng = Number(req.query.lng)
  if (!Number.isFinite(lat) || !Number.isFinite(lng)) {
    return res.status(400).json({ error: 'lat and lng query parameters are required' })
  }
  try {
    const { data } = await axios.get(`${FASTAPI_URL}/pois`, { params: { lat, lng }, timeout: 30000 })
    res.status(200).json(data)
  } catch (err) {
    console.error(err.response?.data || err.message)
    if (err.response) {
      return res.status(502).json({ error: 'POI service error', detail: err.response.data })
    }
    if (err.code === 'ECONNREFUSED') {
      return res.status(503).json({ error: 'POI service unavailable. Is the FastAPI server running?' })
    }
    res.status(500).json({ error: 'Failed to fetch nearby POIs' })
  }
}
module.exports = { getPois }
