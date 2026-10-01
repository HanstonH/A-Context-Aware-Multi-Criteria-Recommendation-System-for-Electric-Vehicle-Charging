const Database = require('better-sqlite3')
const path = require('path')

// The DB lives in the project-root `database/` folder, one level up from the backend.
const dbPath = path.join(__dirname, '..', '..', '..', 'database', 'ev_charging.db')
const db = new Database(dbPath)
db.pragma('foreign_keys = ON')

module.exports = db