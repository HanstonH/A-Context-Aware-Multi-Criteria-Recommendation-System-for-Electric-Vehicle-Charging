const axios = require('axios')
require('dotenv').config()

let cachedToken = null
let tokenExpiry = null

const getTDXToken = async () => {
  // Return cached token if still valid
  if (cachedToken && tokenExpiry && Date.now() < tokenExpiry) {
    return cachedToken
  }

  try {
    const response = await axios.post(
      'https://tdx.transportdata.tw/auth/realms/TDXConnect/protocol/openid-connect/token',
      new URLSearchParams({
        grant_type: 'client_credentials',
        client_id: process.env.TDX_CLIENT_ID,
        client_secret: process.env.TDX_CLIENT_SECRET
      }),
      {
        headers: { 'Content-Type': 'application/x-www-form-urlencoded' }
      }
    )

    cachedToken = response.data.access_token
    // Set expiry a bit earlier than actual expiry to be safe
    tokenExpiry = Date.now() + (response.data.expires_in - 60) * 1000

    return cachedToken
  } catch (err) {
    console.error('Failed to get TDX token:', err.response?.data || err.message)
    throw err
  }
}

module.exports = getTDXToken