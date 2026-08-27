const express = require('express')
const router = express.Router()
const { getStations } = require('../controllers/stationController')

router.get('/:city', getStations)

module.exports = router