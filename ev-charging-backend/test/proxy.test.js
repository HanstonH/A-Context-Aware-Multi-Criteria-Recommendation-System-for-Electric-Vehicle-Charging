// Tests for the routes that forward to the FastAPI recommender.
// axios is stubbed, so FastAPI does NOT need to be running.
const { describe, it, afterEach, mock } = require('node:test')
const assert = require('node:assert/strict')
const { upstreamError, connectionRefused } = require('./helpers')
const axios = require('axios')
const request = require('supertest')
const app = require('../src/app')

// Silence the controllers' console.error output for expected failures.
mock.method(console, 'error', () => {})

afterEach(() => {
  mock.restoreAll()
  mock.method(console, 'error', () => {})
})

describe('GET /', () => {
  it('reports that the API is running', async () => {
    const res = await request(app).get('/')
    assert.equal(res.status, 200)
    assert.match(res.body.message, /running/)
  })
})

describe('POST /api/recommend', () => {
  const body = { lat: 25.033, lng: 121.5654, battery_percent: 40 }

  it('forwards the request to FastAPI and returns its data', async () => {
    const post = mock.method(axios, 'post', async () => ({
      data: { recommendations: [{ StationID: 'S1', topsis_score: 0.9 }] },
    }))
    const res = await request(app).post('/api/recommend').send(body)

    assert.equal(res.status, 200)
    assert.equal(res.body.recommendations[0].StationID, 'S1')
    const [url, payload] = post.mock.calls[0].arguments
    assert.equal(url, 'http://fastapi.test/recommend')
    assert.deepEqual(payload, { ...body, city: 'Taipei' }) // default city
  })

  for (const missing of ['lat', 'lng', 'battery_percent']) {
    it(`returns 400 when ${missing} is missing`, async () => {
      const post = mock.method(axios, 'post', async () => ({ data: {} }))
      const res = await request(app).post('/api/recommend').send({ ...body, [missing]: undefined })
      assert.equal(res.status, 400)
      assert.equal(post.mock.callCount(), 0)
    })
  }

  it('accepts battery_percent = 0 (falsy but valid)', async () => {
    mock.method(axios, 'post', async () => ({ data: { recommendations: [] } }))
    const res = await request(app).post('/api/recommend').send({ ...body, battery_percent: 0 })
    assert.equal(res.status, 200)
  })

  it('returns 400 for an unknown city', async () => {
    const res = await request(app).post('/api/recommend').send({ ...body, city: 'Tokyo' })
    assert.equal(res.status, 400)
    assert.match(res.body.error, /Invalid city/)
  })

  it('returns 502 when FastAPI responds with an error', async () => {
    mock.method(axios, 'post', async () => { throw upstreamError(500, { detail: 'boom' }) })
    const res = await request(app).post('/api/recommend').send(body)
    assert.equal(res.status, 502)
    assert.deepEqual(res.body.detail, { detail: 'boom' })
  })

  it('returns 503 when FastAPI is not running', async () => {
    mock.method(axios, 'post', async () => { throw connectionRefused() })
    const res = await request(app).post('/api/recommend').send(body)
    assert.equal(res.status, 503)
  })

  it('returns 500 on any other failure (e.g. timeout)', async () => {
    mock.method(axios, 'post', async () => { throw Object.assign(new Error('timeout'), { code: 'ECONNABORTED' }) })
    const res = await request(app).post('/api/recommend').send(body)
    assert.equal(res.status, 500)
  })
})

describe('GET /api/stations/:city', () => {
  it('returns stations for a valid city', async () => {
    const get = mock.method(axios, 'get', async () => ({ data: { stations: [{ StationID: 'A' }] } }))
    const res = await request(app).get('/api/stations/Taipei')
    assert.equal(res.status, 200)
    assert.equal(res.body.stations.length, 1)
    assert.equal(get.mock.calls[0].arguments[0], 'http://fastapi.test/stations/Taipei')
  })

  it('returns 400 for an unknown city without calling FastAPI', async () => {
    const get = mock.method(axios, 'get', async () => ({ data: {} }))
    const res = await request(app).get('/api/stations/Atlantis')
    assert.equal(res.status, 400)
    assert.equal(get.mock.callCount(), 0)
  })

  it('returns 503 when FastAPI is not running', async () => {
    mock.method(axios, 'get', async () => { throw connectionRefused() })
    const res = await request(app).get('/api/stations/Taipei')
    assert.equal(res.status, 503)
  })
})

describe('GET /api/pois', () => {
  it('forwards numeric lat/lng to FastAPI', async () => {
    const get = mock.method(axios, 'get', async () => ({ data: { pois: [] } }))
    const res = await request(app).get('/api/pois').query({ lat: '25.03', lng: '121.56' })
    assert.equal(res.status, 200)
    assert.deepEqual(get.mock.calls[0].arguments[1].params, { lat: 25.03, lng: 121.56 })
  })

  it('returns 400 for non-numeric coordinates', async () => {
    const res = await request(app).get('/api/pois').query({ lat: 'abc', lng: '121.56' })
    assert.equal(res.status, 400)
  })

  it('returns 502 when the Places lookup fails upstream', async () => {
    mock.method(axios, 'get', async () => { throw upstreamError(502, { detail: 'Places API request failed' }) })
    const res = await request(app).get('/api/pois').query({ lat: 25.03, lng: 121.56 })
    assert.equal(res.status, 502)
  })
})

describe('GET /api/route', () => {
  const query = { from_lat: 25.0, from_lng: 121.5, to_lat: 25.1, to_lng: 121.6 }

  it('returns the route points from FastAPI', async () => {
    mock.method(axios, 'get', async () => ({ data: { route: [[25.0, 121.5], [25.1, 121.6]] } }))
    const res = await request(app).get('/api/route').query(query)
    assert.equal(res.status, 200)
    assert.equal(res.body.route.length, 2)
  })

  it('returns 400 when a coordinate is missing', async () => {
    const res = await request(app).get('/api/route').query({ ...query, to_lng: undefined })
    assert.equal(res.status, 400)
  })

  it('returns 502 when FastAPI finds no route', async () => {
    mock.method(axios, 'get', async () => { throw upstreamError(404, { detail: 'No route found' }) })
    const res = await request(app).get('/api/route').query(query)
    assert.equal(res.status, 502)
  })
})
