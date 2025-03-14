/**
 * Service for file operations.
 */
const fs = require('fs');
const path = require('path');
const { ApiError } = require('../utils/errorHandler');

/**
 * Create a new file record in the database
 */
const createFile = async (pool, fileData) => {
  const { id, user_id, filename, filepath, filetype, filesize } = fileData;
  
  try {
    const result = await pool.query(
      `INSERT INTO input_files
        (id, user_id, file_name, file_path, file_type, file_size, created_at)
      VALUES
        ($1, $2, $3, $4, $5, $6, NOW())
      RETURNING *`,
      [id, user_id, filename, filepath, filetype, filesize]
    );
    
    return result.rows[0];
  } catch (error) {
    throw new ApiError(`Failed to create file record: ${error.message}`, 500);
  }
};

/**
 * Get all files from the database
 */
const getFiles = async (pool, userId = null) => {
  try {
    let query = `
      SELECT * FROM input_files
      ORDER BY created_at DESC
    `;
    
    let queryParams = [];
    
    if (userId) {
      query = `
        SELECT * FROM input_files
        WHERE user_id = $1
        ORDER BY created_at DESC
      `;
      queryParams = [userId];
    }
    
    const result = await pool.query(query, queryParams);
    return result.rows;
  } catch (error) {
    throw new ApiError(`Failed to get files: ${error.message}`, 500);
  }
};

/**
 * Get a specific file by ID
 */
const getFileById = async (pool, fileId) => {
  try {
    const result = await pool.query(
      'SELECT * FROM input_files WHERE id = $1',
      [fileId]
    );
    
    if (result.rows.length === 0) {
      return null;
    }
    
    return result.rows[0];
  } catch (error) {
    throw new ApiError(`Failed to get file: ${error.message}`, 500);
  }
};

/**
 * Delete a file from the database and filesystem
 */
const deleteFile = async (pool, fileId) => {
  try {
    // Get file information first
    const file = await getFileById(pool, fileId);
    
    if (!file) {
      throw new ApiError(`File not found: ${fileId}`, 404);
    }
    
    // Delete file from database
    const result = await pool.query(
      'DELETE FROM input_files WHERE id = $1 RETURNING *',
      [fileId]
    );
    
    // Delete file from filesystem if it exists
    if (fs.existsSync(file.file_path)) {
      fs.unlinkSync(file.file_path);
    }
    
    return result.rows[0];
  } catch (error) {
    if (error instanceof ApiError) {
      throw error;
    }
    throw new ApiError(`Failed to delete file: ${error.message}`, 500);
  }
};

/**
 * Get file mime type based on extension
 */
const getMimeType = (filePath) => {
  const extension = path.extname(filePath).toLowerCase();
  
  const mimeTypes = {
    '.csv': 'text/csv',
    '.txt': 'text/plain',
    '.json': 'application/json',
    '.pdf': 'application/pdf',
    '.xls': 'application/vnd.ms-excel',
    '.xlsx': 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
    '.doc': 'application/msword',
    '.docx': 'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
  };
  
  return mimeTypes[extension] || 'application/octet-stream';
};

module.exports = {
  createFile,
  getFiles,
  getFileById,
  deleteFile,
  getMimeType
};