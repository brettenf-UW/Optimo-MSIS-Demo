/**
 * Error handling utilities.
 */

/**
 * Custom API error class
 */
class ApiError extends Error {
  constructor(message, status = 500, details = null) {
    super(message);
    this.status = status;
    this.details = details;
    this.name = this.constructor.name;
  }
  
  static badRequest(message, details = null) {
    return new ApiError(message, 400, details);
  }
  
  static unauthorized(message = 'Unauthorized', details = null) {
    return new ApiError(message, 401, details);
  }
  
  static forbidden(message = 'Forbidden', details = null) {
    return new ApiError(message, 403, details);
  }
  
  static notFound(message = 'Resource not found', details = null) {
    return new ApiError(message, 404, details);
  }
  
  static conflict(message, details = null) {
    return new ApiError(message, 409, details);
  }
  
  static internal(message = 'Internal server error', details = null) {
    return new ApiError(message, 500, details);
  }
}

/**
 * Handle async route errors
 */
const asyncHandler = (fn) => (req, res, next) => {
  Promise.resolve(fn(req, res, next)).catch(next);
};

/**
 * Format database errors
 */
const formatDbError = (error) => {
  if (error.code === '23505') {
    // Unique constraint violation
    return ApiError.conflict('Resource already exists', { constraint: error.constraint });
  }
  
  if (error.code === '23503') {
    // Foreign key constraint violation
    return ApiError.badRequest('Referenced resource does not exist', { constraint: error.constraint });
  }
  
  // Default database error
  return ApiError.internal('Database error', { code: error.code });
};

module.exports = {
  ApiError,
  asyncHandler,
  formatDbError
};