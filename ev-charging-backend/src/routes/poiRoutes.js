const express = require('express')
const router = express.Router()
const { getPois } = require('../controllers/poiController')
router.get('/', getPois)
module.exports = router
