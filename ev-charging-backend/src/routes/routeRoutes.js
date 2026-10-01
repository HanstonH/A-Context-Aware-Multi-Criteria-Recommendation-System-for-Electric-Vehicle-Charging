const express = require('express')
const router = express.Router()
const { getRoute } = require('../controllers/routeController')
router.get('/', getRoute)
module.exports = router