const axios = require('axios')
const { FASTAPI_URL, TDX_CITIES } = require('../config/constants')

const handleError = (err, res) => {
  console.error(err.response?.data || err.message)
  if (err.response) {
    return res.status(502).json({ error: 'Station service error', detail: err.response.data })
  }
  if (err.code === 'ECONNREFUSED') {
    return res.status(503).json({ error: 'Station service unavailable. Is the FastAPI server running?' })
  }
  res.status(500).json({ error: 'Failed to fetch station data' })
}

// Every station in Taiwan (about 3,000), for drawing all pins on the map.
const getAllStations = async (req, res) => {
  try {
    const { data } = await axios.get(`${FASTAPI_URL}/stations`, { timeout: 30000 })
    res.status(200).json(data)
  } catch (err) {
    handleError(err, res)
  }
}

const getStations = async (req, res) => {
  const { city } = req.params
  if (!TDX_CITIES.includes(city)) {
    return res.status(400).json({ error: `Invalid city. Must be one of: ${TDX_CITIES.join(', ')}` })
  }
  try {
    const { data } = await axios.get(`${FASTAPI_URL}/stations/${city}`, { timeout: 30000 })
    res.status(200).json(data)
  } catch (err) {
    handleError(err, res)
  }
}

module.exports = { getAllStations, getStations }
