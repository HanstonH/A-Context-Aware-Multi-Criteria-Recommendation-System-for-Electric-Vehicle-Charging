const express = require('express')
const cors = require('cors')

const authRoutes = require('./routes/authRoutes')
const stationRoutes = require('./routes/stationRoutes')
const recommendRoutes = require('./routes/recommendRoutes')
const poiRoutes = require('./routes/poiRoutes')
const routeRoutes = require('./routes/routeRoutes')

// The Express app is built here (without calling listen) so tests can
// import it and send requests with supertest, without opening a real port.
const app = express()

// Middleware
app.use(cors())
app.use(express.json())

// Routes
app.use('/api/stations', stationRoutes)
app.use('/api/pois', poiRoutes)
app.use('/api/auth', authRoutes)
app.use('/api/route', routeRoutes)
app.use('/api/recommend', recommendRoutes)

// Test route
app.get('/', (req, res) => {
  res.json({ message: 'EV Charging API is running' })
})

module.exports = app
