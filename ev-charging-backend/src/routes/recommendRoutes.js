const express = require('express')
const router = express.Router()
const { getRecommendations } = require('../controllers/recommendController')
router.post('/', getRecommendations)
module.exports = router