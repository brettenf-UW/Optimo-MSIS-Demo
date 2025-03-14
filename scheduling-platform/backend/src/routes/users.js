/**
 * Routes for user operations.
 */
const express = require('express');
const { login, register, getProfile, updateProfile } = require('../controllers/userController');
const { authenticate } = require('../middleware/auth');

module.exports = (pool, logger) => {
  const router = express.Router();

  /**
   * @route POST /api/users/login
   * @description Authenticate user and get token
   * @access Public
   */
  router.post('/login', login(pool, logger));

  /**
   * @route POST /api/users/register
   * @description Register a new user
   * @access Public
   */
  router.post('/register', register(pool, logger));

  /**
   * @route GET /api/users/me
   * @description Get current user profile
   * @access Private
   */
  router.get('/me', authenticate, getProfile(pool, logger));

  /**
   * @route PUT /api/users/me
   * @description Update user profile
   * @access Private
   */
  router.put('/me', authenticate, updateProfile(pool, logger));

  return router;
};
