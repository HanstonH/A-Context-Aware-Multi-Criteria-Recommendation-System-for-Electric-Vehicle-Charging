const express = require('express')
const cors = require('cors')
require('dotenv').config()

const authRoutes = require('./src/routes/authRoutes')
const stationRoutes = require('./src/routes/stationRoutes')
const recommendRoutes = require('./src/routes/recommendRoutes')
const poiRoutes = require('./src/routes/poiRoutes')
const routeRoutes = require('./src/routes/routeRoutes')

const app = express()
const PORT = process.env.PORT || 5000

// Middleware
app.use(cors())
app.use(express.json())

// Routes
app.use('/api/auth', authRoutes)
app.use('/api/stations', stationRoutes)
app.use('/api/recommend', recommendRoutes)
app.use('/api/pois', poiRoutes)
app.use('/api/route', routeRoutes)

// Test route
app.get('/', (req, res) => {
  res.json({ message: 'EV Charging API is running' })
})

// Start server
app.listen(PORT, () => {
  console.log(`Server running on port ${PORT}`)
})
