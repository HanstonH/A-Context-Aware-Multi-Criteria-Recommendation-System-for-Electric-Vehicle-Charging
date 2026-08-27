const axios = require('axios')
const TDX_CITIES = [
  'Taipei', 'NewTaipei', 'Taoyuan', 'Taichung', 'Tainan', 'Kaohsiung',
  'Keelung', 'Hsinchu', 'HsinchuCounty', 'MiaoliCounty', 'ChanghuaCounty',
  'NantouCounty', 'YunlinCounty', 'ChiayiCounty', 'Chiayi', 'PingtungCounty',
  'YilanCounty', 'HualienCounty', 'TaitungCounty', 'KinmenCounty',
  'PenghuCounty', 'LienchiangCounty'
]
const FASTAPI_URL = process.env.FASTAPI_URL || 'http://localhost:8000'
const getStations = async (req, res) => {
  const { city } = req.params
  if (!TDX_CITIES.includes(city)) {
    return res.status(400).json({ error: `Invalid city. Must be one of: ${TDX_CITIES.join(', ')}` })
  }
  try {
    const { data } = await axios.get(`${FASTAPI_URL}/stations/${city}`, { timeout: 30000 })
    res.status(200).json(data)
  } catch (err) {
    console.error(err.response?.data || err.message)
    if (err.response) {
      return res.status(502).json({ error: 'Station service error', detail: err.response.data })
    }
    if (err.code === 'ECONNREFUSED') {
      return res.status(503).json({ error: 'Station service unavailable. Is the FastAPI server running?' })
    }
    res.status(500).json({ error: 'Failed to fetch station data' })
  }
}
module.exports = { getStations }