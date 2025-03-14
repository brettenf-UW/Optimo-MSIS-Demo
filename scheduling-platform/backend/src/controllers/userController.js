/**
 * Controllers for user operations.
 */
const bcrypt = require('bcryptjs');
const jwt = require('jsonwebtoken');
const userService = require('../services/userService');

/**
 * Login a user
 */
const login = (pool, logger) => async (req, res, next) => {
  try {
    const { email, password } = req.body;
    
    if (!email || !password) {
      return res.status(400).json({ error: 'Email and password are required' });
    }
    
    // Get user from database
    const user = await userService.getUserByEmail(pool, email);
    
    if (!user) {
      return res.status(401).json({ error: 'Invalid credentials' });
    }
    
    // Compare passwords
    const isMatch = await bcrypt.compare(password, user.password_hash);
    
    if (!isMatch) {
      return res.status(401).json({ error: 'Invalid credentials' });
    }
    
    // Create JWT token
    const tokenPayload = {
      id: user.id,
      email: user.email,
      role: user.role
    };
    
    const token = jwt.sign(
      tokenPayload,
      process.env.JWT_SECRET || 'your-secret-key',
      { expiresIn: '1d' }
    );
    
    res.json({
      token,
      user: {
        id: user.id,
        email: user.email,
        username: user.username,
        role: user.role
      }
    });
  } catch (error) {
    logger.error('Error logging in user', { error });
    next(error);
  }
};

/**
 * Register a new user
 */
const register = (pool, logger) => async (req, res, next) => {
  try {
    const { username, email, password, role } = req.body;
    
    if (!username || !email || !password) {
      return res.status(400).json({ error: 'Username, email, and password are required' });
    }
    
    // Check if user already exists
    const existingUser = await userService.getUserByEmail(pool, email);
    
    if (existingUser) {
      return res.status(400).json({ error: 'User already exists' });
    }
    
    // Hash password
    const salt = await bcrypt.genSalt(10);
    const passwordHash = await bcrypt.hash(password, salt);
    
    // Create user
    const newUser = await userService.createUser(pool, {
      username,
      email,
      password_hash: passwordHash,
      role: role || 'user'
    });
    
    // Create JWT token
    const tokenPayload = {
      id: newUser.id,
      email: newUser.email,
      role: newUser.role
    };
    
    const token = jwt.sign(
      tokenPayload,
      process.env.JWT_SECRET || 'your-secret-key',
      { expiresIn: '1d' }
    );
    
    res.status(201).json({
      token,
      user: {
        id: newUser.id,
        email: newUser.email,
        username: newUser.username,
        role: newUser.role
      }
    });
  } catch (error) {
    logger.error('Error registering user', { error });
    next(error);
  }
};

/**
 * Get current user profile
 */
const getProfile = (pool, logger) => async (req, res, next) => {
  try {
    const user = await userService.getUserById(pool, req.user.id);
    
    if (!user) {
      return res.status(404).json({ error: 'User not found' });
    }
    
    res.json({
      id: user.id,
      email: user.email,
      username: user.username,
      role: user.role,
      created_at: user.created_at
    });
  } catch (error) {
    logger.error('Error getting user profile', { error });
    next(error);
  }
};

/**
 * Update user profile
 */
const updateProfile = (pool, logger) => async (req, res, next) => {
  try {
    const { username, email, password } = req.body;
    const updates = {};
    
    if (username) updates.username = username;
    if (email) updates.email = email;
    
    if (password) {
      const salt = await bcrypt.genSalt(10);
      updates.password_hash = await bcrypt.hash(password, salt);
    }
    
    if (Object.keys(updates).length === 0) {
      return res.status(400).json({ error: 'No updates provided' });
    }
    
    const updatedUser = await userService.updateUser(pool, req.user.id, updates);
    
    res.json({
      id: updatedUser.id,
      email: updatedUser.email,
      username: updatedUser.username,
      role: updatedUser.role,
      updated_at: updatedUser.updated_at
    });
  } catch (error) {
    logger.error('Error updating user profile', { error });
    next(error);
  }
};

module.exports = {
  login,
  register,
  getProfile,
  updateProfile
};
