const supabase = require('../config/supabase')
const bcrypt = require('bcrypt')

// Register
const register = async (req, res) => {
  const { email, password, name, phone } = req.body

  try {
    const hashedPassword = await bcrypt.hash(password, 10)

    const { data, error } = await supabase
      .from('users')
      .insert([{ email, password: hashedPassword, name, phone }])
      .select()

    if (error) return res.status(400).json({ error: error.message })

    res.status(201).json({ message: 'User registered successfully', user: data[0] })
  } catch (err) {
    res.status(500).json({ error: 'Server error' })
  }
}

// Login
const login = async (req, res) => {
  const { email, password } = req.body

  try {
    const { data, error } = await supabase
      .from('users')
      .select('*')
      .eq('email', email)
      .single()

    if (error || !data) return res.status(404).json({ error: 'User not found' })

    const validPassword = await bcrypt.compare(password, data.password)
    if (!validPassword) return res.status(401).json({ error: 'Invalid password' })

    const { password: _, ...userWithoutPassword } = data

    res.status(200).json({ message: 'Login successful', user: userWithoutPassword })
  } catch (err) {
    res.status(500).json({ error: 'Server error' })
  }
}

module.exports = { register, login }