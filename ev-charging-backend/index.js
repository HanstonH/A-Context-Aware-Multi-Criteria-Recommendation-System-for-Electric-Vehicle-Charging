const express = require('express')
const cors = require('cors')
require('dotenv').config()

const authRoutes = require('./src/routes/authRoutes')

const app = express()
const PORT = process.env.PORT || 5000

const stationRoutes = require('./src/routes/stationRoutes')

const recommendRoutes = require('./src/routes/recommendRoutes')

// Middleware
app.use(cors())
app.use(express.json())
app.use('/api/stations', stationRoutes)

// Routes
app.use('/api/auth', authRoutes)

// Test route
app.get('/', (req, res) => {
  res.json({ message: 'EV Charging API is running' })
})

// Start server
app.listen(PORT, () => {
  console.log(`Server running on port ${PORT}`)
})

app.use('/api/recommend', recommendRoutes)