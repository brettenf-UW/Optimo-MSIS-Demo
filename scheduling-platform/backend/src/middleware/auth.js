/**
 * Authentication middleware.
 */
const jwt = require('jsonwebtoken');

/**
 * Authenticate a user by JWT token
 */
const authenticate = (req, res, next) => {
  // Get token from header
  const token = req.header('Authorization')?.replace('Bearer ', '');
  
  if (!token) {
    return res.status(401).json({ error: 'No token, authorization denied' });
  }
  
  try {
    // Verify token
    const decoded = jwt.verify(token, process.env.JWT_SECRET || 'your-secret-key');
    
    // Add user to request
    req.user = decoded;
    
    next();
  } catch (error) {
    res.status(401).json({ error: 'Token is not valid' });
  }
};

/**
 * Check if user has admin role
 */
const requireAdmin = (req, res, next) => {
  if (!req.user || req.user.role !== 'admin') {
    return res.status(403).json({ error: 'Access denied, admin privileges required' });
  }
  
  next();
};

module.exports = {
  authenticate,
  requireAdmin
};