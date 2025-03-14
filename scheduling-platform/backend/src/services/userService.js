/**
 * Service for user operations.
 */
const { ApiError } = require('../utils/errorHandler');

/**
 * Create a new user in the database
 */
const createUser = async (pool, userData) => {
  const { username, email, password_hash, role } = userData;
  
  try {
    const result = await pool.query(
      `INSERT INTO users
        (username, email, password_hash, role, created_at, updated_at)
      VALUES
        ($1, $2, $3, $4, NOW(), NOW())
      RETURNING id, username, email, role, created_at`,
      [username, email, password_hash, role]
    );
    
    return result.rows[0];
  } catch (error) {
    // Check for unique constraint violation
    if (error.code === '23505') {
      if (error.constraint === 'users_email_key') {
        throw new ApiError('Email already in use', 400);
      }
      if (error.constraint === 'users_username_key') {
        throw new ApiError('Username already in use', 400);
      }
    }
    
    throw new ApiError(`Failed to create user: ${error.message}`, 500);
  }
};

/**
 * Get a user by email
 */
const getUserByEmail = async (pool, email) => {
  try {
    const result = await pool.query(
      'SELECT * FROM users WHERE email = $1',
      [email]
    );
    
    if (result.rows.length === 0) {
      return null;
    }
    
    return result.rows[0];
  } catch (error) {
    throw new ApiError(`Failed to get user by email: ${error.message}`, 500);
  }
};

/**
 * Get a user by ID
 */
const getUserById = async (pool, userId) => {
  try {
    const result = await pool.query(
      'SELECT * FROM users WHERE id = $1',
      [userId]
    );
    
    if (result.rows.length === 0) {
      return null;
    }
    
    return result.rows[0];
  } catch (error) {
    throw new ApiError(`Failed to get user by ID: ${error.message}`, 500);
  }
};

/**
 * Update a user
 */
const updateUser = async (pool, userId, updates) => {
  try {
    // Construct dynamic update query
    const updateFields = [];
    const updateValues = [];
    let valueIndex = 1;
    
    for (const [key, value] of Object.entries(updates)) {
      updateFields.push(`${key} = $${valueIndex}`);
      updateValues.push(value);
      valueIndex++;
    }
    
    // Add updated_at timestamp
    updateFields.push(`updated_at = NOW()`);
    
    // Add user ID to parameters
    updateValues.push(userId);
    
    const query = `
      UPDATE users
      SET ${updateFields.join(', ')}
      WHERE id = $${valueIndex}
      RETURNING id, username, email, role, updated_at
    `;
    
    const result = await pool.query(query, updateValues);
    
    if (result.rows.length === 0) {
      throw new ApiError(`User not found: ${userId}`, 404);
    }
    
    return result.rows[0];
  } catch (error) {
    // Check for unique constraint violation
    if (error.code === '23505') {
      if (error.constraint === 'users_email_key') {
        throw new ApiError('Email already in use', 400);
      }
      if (error.constraint === 'users_username_key') {
        throw new ApiError('Username already in use', 400);
      }
    }
    
    if (error instanceof ApiError) {
      throw error;
    }
    
    throw new ApiError(`Failed to update user: ${error.message}`, 500);
  }
};

/**
 * Delete a user
 */
const deleteUser = async (pool, userId) => {
  try {
    const result = await pool.query(
      'DELETE FROM users WHERE id = $1 RETURNING id',
      [userId]
    );
    
    if (result.rows.length === 0) {
      throw new ApiError(`User not found: ${userId}`, 404);
    }
    
    return true;
  } catch (error) {
    if (error instanceof ApiError) {
      throw error;
    }
    
    throw new ApiError(`Failed to delete user: ${error.message}`, 500);
  }
};

module.exports = {
  createUser,
  getUserByEmail,
  getUserById,
  updateUser,
  deleteUser
};