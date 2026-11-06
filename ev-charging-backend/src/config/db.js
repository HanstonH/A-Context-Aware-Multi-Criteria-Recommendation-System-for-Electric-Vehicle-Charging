const Database = require('better-sqlite3')
const path = require('path')

// The DB lives in the project-root `database/` folder, one level up from the backend.
// DB_PATH can override it (the test suite points it at a throw-away database).
const dbPath =
  process.env.DB_PATH || path.join(__dirname, '..', '..', '..', 'database', 'ev_charging.db')
const db = new Database(dbPath)
db.pragma('foreign_keys = ON')

module.exports = db
