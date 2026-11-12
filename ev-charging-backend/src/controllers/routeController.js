const axios = require('axios')
const FASTAPI_URL = process.env.FASTAPI_URL || 'http://127.0.0.1:8000'
const getRoute = async (req, res) => {
  const { from_lat, from_lng, to_lat, to_lng } = req.query
  if (from_lat == null || from_lng == null || to_lat == null || to_lng == null) {
    return res.status(400).json({ error: 'from_lat, from_lng, to_lat, to_lng are required' })
  }
  try {
    const { data } = await axios.get(`${FASTAPI_URL}/route`, {
      params: { from_lat, from_lng, to_lat, to_lng },
      timeout: 30000,
    })
    res.status(200).json(data)
  } catch (err) {
    console.error(err.response?.data || err.message)
    if (err.response) {
      return res.status(502).json({ error: 'Route service error', detail: err.response.data })
    }
    if (err.code === 'ECONNREFUSED') {
      return res.status(503).json({ error: 'Route service unavailable. Is the FastAPI server running?' })
    }
    res.status(500).json({ error: 'Failed to fetch route' })
  }
}
module.exports = { getRoute }