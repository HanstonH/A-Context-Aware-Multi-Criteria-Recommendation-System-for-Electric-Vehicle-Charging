// Tests for /api/auth against a throw-away SQLite database (see helpers.js).
const { describe, it, before, mock } = require('node:test')
const assert = require('node:assert/strict')
const { dbPath } = require('./helpers')
const Database = require('better-sqlite3')
const request = require('supertest')
const app = require('../src/app')

mock.method(console, 'error', () => {})

const user = { email: 'driver@example.com', password: 's3cret!', name: 'Test Driver', phone: '0912345678' }

describe('POST /api/auth/register', () => {
  it('creates a user and never returns the password hash', async () => {
    const res = await request(app).post('/api/auth/register').send(user)
    assert.equal(res.status, 201)
    assert.equal(res.body.user.email, user.email)
    assert.equal(res.body.user.password_hash, undefined)
    assert.equal(res.body.user.password, undefined)
  })

  it('stores a bcrypt hash, not the plain-text password', () => {
    const db = new Database(dbPath, { readonly: true })
    const row = db.prepare('SELECT password_hash FROM users WHERE email = ?').get(user.email)
    db.close()
    assert.notEqual(row.password_hash, user.password)
    assert.match(row.password_hash, /^\$2[aby]\$/)
  })

  it('rejects a duplicate email', async () => {
    const res = await request(app).post('/api/auth/register').send(user)
    assert.equal(res.status, 400)
    assert.match(res.body.error, /already registered/)
  })

  it('requires email and password', async () => {
    const res = await request(app).post('/api/auth/register').send({ email: 'x@example.com' })
    assert.equal(res.status, 400)
  })
})

describe('POST /api/auth/login', () => {
  before(async () => {
    await request(app).post('/api/auth/register').send({ email: 'login@example.com', password: 'pw123456' })
  })

  it('logs in with the correct password', async () => {
    const res = await request(app).post('/api/auth/login').send({ email: 'login@example.com', password: 'pw123456' })
    assert.equal(res.status, 200)
    assert.equal(res.body.user.email, 'login@example.com')
    assert.equal(res.body.user.password_hash, undefined)
  })

  it('rejects a wrong password with 401', async () => {
    const res = await request(app).post('/api/auth/login').send({ email: 'login@example.com', password: 'nope' })
    assert.equal(res.status, 401)
  })

  it('returns 404 for an unknown email', async () => {
    const res = await request(app).post('/api/auth/login').send({ email: 'ghost@example.com', password: 'x' })
    assert.equal(res.status, 404)
  })
})
