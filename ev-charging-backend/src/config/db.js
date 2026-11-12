const Database = require('better-sqlite3')
const fs = require('fs')
const path = require('path')

// Local default: the project-root `database/` folder, one level up from the backend.
// In production set DB_PATH to a file on a persistent volume (e.g. /data/ev_charging.db),
// otherwise every redeploy starts with an empty database.
const projectDatabaseDir = path.join(__dirname, '..', '..', '..', 'database')
const dbPath = process.env.DB_PATH || path.join(projectDatabaseDir, 'ev_charging.db')
const schemaPath = process.env.DB_SCHEMA_PATH || path.join(projectDatabaseDir, 'schema.sql')

fs.mkdirSync(path.dirname(dbPath), { recursive: true })
const db = new Database(dbPath)
db.pragma('foreign_keys = ON')

// Create any missing tables. schema.sql only uses CREATE ... IF NOT EXISTS,
// so this is safe to run on every start and never touches existing data.
db.exec(fs.readFileSync(schemaPath, 'utf8'))

console.log(`SQLite database: ${dbPath}`)

module.exports = db
