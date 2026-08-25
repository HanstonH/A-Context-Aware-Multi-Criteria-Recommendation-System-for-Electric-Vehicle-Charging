const axios = require('axios')
const getTDXToken = require('../config/tdx')

const BASE_URL = 'https://tdx.transportdata.tw/api/basic/v1/EV'

const TDX_CITIES = [
  'Taipei', 'NewTaipei', 'Taoyuan', 'Taichung', 'Tainan', 'Kaohsiung',
  'Keelung', 'Hsinchu', 'HsinchuCounty', 'MiaoliCounty', 'ChanghuaCounty',
  'NantouCounty', 'YunlinCounty', 'ChiayiCounty', 'Chiayi', 'PingtungCounty',
  'YilanCounty', 'HualienCounty', 'TaitungCounty', 'KinmenCounty',
  'PenghuCounty', 'LienchiangCounty'
]

const getStations = async (req, res) => {
  const { city } = req.params

  if (!TDX_CITIES.includes(city)) {
    return res.status(400).json({ error: `Invalid city. Must be one of: ${TDX_CITIES.join(', ')}` })
  }

  try {
    const token = await getTDXToken()
    const headers = { Authorization: `Bearer ${token}` }
    const params = { '$format': 'JSON' }

    const [stationRes, liveStatusRes, rateRes] = await Promise.all([
      axios.get(`${BASE_URL}/Station/City/${city}`, { headers, params }),
      axios.get(`${BASE_URL}/ConnectorLiveStatus/City/${city}`, { headers, params }),
      axios.get(`${BASE_URL}/ChargingRate/City/${city}`, { headers, params })
    ])

    res.status(200).json({
      stations: stationRes.data,
      liveStatus: liveStatusRes.data,
      rates: rateRes.data
    })
  } catch (err) {
    console.error(err.response?.data || err.message)
    res.status(500).json({ error: 'Failed to fetch station data' })
  }
}

module.exports = { getStations }