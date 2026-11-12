const express = require('express')
const router = express.Router()
const { getAllStations, getStations } = require('../controllers/stationController')

router.get('/', getAllStations)
router.get('/:city', getStations)

module.exports = router
