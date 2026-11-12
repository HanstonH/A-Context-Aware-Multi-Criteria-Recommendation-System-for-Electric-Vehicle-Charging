// Shared settings for the controllers that forward requests to the FastAPI service.

// 127.0.0.1 rather than localhost: uvicorn binds to IPv4 by default, and on some
// Windows setups `localhost` resolves to IPv6 (::1) first. Matches the frontend default.
const FASTAPI_URL = process.env.FASTAPI_URL || 'http://127.0.0.1:8000'

// City codes accepted by TDX (and by the FastAPI service).
const TDX_CITIES = [
  'Taipei', 'NewTaipei', 'Taoyuan', 'Taichung', 'Tainan', 'Kaohsiung',
  'Keelung', 'Hsinchu', 'HsinchuCounty', 'MiaoliCounty', 'ChanghuaCounty',
  'NantouCounty', 'YunlinCounty', 'ChiayiCounty', 'Chiayi', 'PingtungCounty',
  'YilanCounty', 'HualienCounty', 'TaitungCounty', 'KinmenCounty',
  'PenghuCounty', 'LienchiangCounty'
]

module.exports = { FASTAPI_URL, TDX_CITIES }
