// Shared test setup. Require this BEFORE requiring ../src/app so that the
// database module picks up the throw-away DB_PATH instead of the real
// database/ev_charging.db.
const fs = require('fs')
const os = require('os')
const path = require('path')
const Database = require('better-sqlite3')

const tmpDir = fs.mkdtempSync(path.join(os.tmpdir(), 'ev-backend-test-'))
const dbPath = path.join(tmpDir, 'test.db')
const schema = fs.readFileSync(path.join(__dirname, '..', '..', 'database', 'schema.sql'), 'utf8')

const setup = new Database(dbPath)
setup.exec(schema)
setup.close()

process.env.DB_PATH = dbPath
process.env.FASTAPI_URL = 'http://fastapi.test'

/** Build an axios-style error, as thrown when FastAPI answers 4xx/5xx. */
function upstreamError(status, data) {
  const err = new Error(`Request failed with status code ${status}`)
  err.response = { status, data }
  return err
}

/** Build the error axios throws when nothing is listening on FASTAPI_URL. */
function connectionRefused() {
  const err = new Error('connect ECONNREFUSED 127.0.0.1:8000')
  err.code = 'ECONNREFUSED'
  return err
}

module.exports = { dbPath, upstreamError, connectionRefused }
