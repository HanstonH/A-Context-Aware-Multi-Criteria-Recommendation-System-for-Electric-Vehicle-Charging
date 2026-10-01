const db = require('../config/db')
const bcrypt = require('bcrypt')

// Register
const register = async (req, res) => {
  const { email, password, name, phone } = req.body
  if (!email || !password) {
    return res.status(400).json({ error: 'Email and password are required' })
  }
  try {
    const hashedPassword = await bcrypt.hash(password, 10)
    const info = db
      .prepare('INSERT INTO users (email, password_hash, name, phone) VALUES (?, ?, ?, ?)')
      .run(email, hashedPassword, name, phone)

    const user = db
      .prepare('SELECT id, email, name, phone, created_at FROM users WHERE id = ?')
      .get(info.lastInsertRowid)

    res.status(201).json({ message: 'User registered successfully', user })
  } catch (err) {
    if (err.code === 'SQLITE_CONSTRAINT_UNIQUE') {
      return res.status(400).json({ error: 'Email already registered' })
    }
    console.error(err.message)
    res.status(500).json({ error: 'Server error' })
  }
}

// Login
const login = async (req, res) => {
  const { email, password } = req.body
  try {
    const user = db.prepare('SELECT * FROM users WHERE email = ?').get(email)
    if (!user) return res.status(404).json({ error: 'User not found' })

    const validPassword = await bcrypt.compare(password, user.password_hash)
    if (!validPassword) return res.status(401).json({ error: 'Invalid password' })

    const { password_hash: _, ...userWithoutPassword } = user
    res.status(200).json({ message: 'Login successful', user: userWithoutPassword })
  } catch (err) {
    console.error(err.message)
    res.status(500).json({ error: 'Server error' })
  }
}

module.exports = { register, login }