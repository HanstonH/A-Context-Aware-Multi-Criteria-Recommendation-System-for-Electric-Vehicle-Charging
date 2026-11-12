const axios = require('axios')
const { FASTAPI_URL, TDX_CITIES } = require('../config/constants')
const getRecommendations = async (req, res) => {
  const body = req.body || {}
  const { city } = body
  // Number(null) and Number('') are 0, so rule out missing values before converting.
  const missing = ['lat', 'lng', 'battery_percent'].filter(k => body[k] == null || body[k] === '')
  if (missing.length) {
    return res.status(400).json({ error: 'lat, lng, and battery_percent are required' })
  }
  const lat = Number(body.lat)
  const lng = Number(body.lng)
  const battery_percent = Number(body.battery_percent)
  if (!Number.isFinite(lat) || !Number.isFinite(lng) || !Number.isFinite(battery_percent)) {
    return res.status(400).json({ error: 'lat, lng, and battery_percent must be numbers' })
  }
  if (battery_percent < 0 || battery_percent > 100) {
    return res.status(400).json({ error: 'battery_percent must be between 0 and 100' })
  }
  if (city && !TDX_CITIES.includes(city)) {
    return res.status(400).json({ error: `Invalid city. Must be one of: ${TDX_CITIES.join(', ')}` })
  }
  // "Need it now" mode: favour close stations with free chargers over price.
  const is_available_now = body.is_available_now === true
  // No city → FastAPI searches stations across all of Taiwan.
  const forwarded = { lat, lng, battery_percent, is_available_now }
  if (city) forwarded.city = city
  try {
    const { data } = await axios.post(
      `${FASTAPI_URL}/recommend`,
      forwarded,
      { timeout: 30000 }
    )
    res.status(200).json(data)
  } catch (err) {
    console.error(err.response?.data || err.message)
    if (err.response) {
      return res.status(502).json({ error: 'Recommendation service error', detail: err.response.data })
    }
    if (err.code === 'ECONNREFUSED') {
      return res.status(503).json({ error: 'Recommendation service unavailable. Is the FastAPI server running?' })
    }
    res.status(500).json({ error: 'Failed to fetch recommendations' })
  }
}
module.exports = { getRecommendations }