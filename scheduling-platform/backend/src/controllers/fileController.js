/**
 * Controllers for file operations.
 */
const fs = require('fs');
const path = require('path');
const { v4: uuidv4 } = require('uuid');
const fileService = require('../services/fileService');

/**
 * Upload a file
 */
const uploadFile = (pool, logger) => async (req, res, next) => {
  try {
    if (!req.file) {
      return res.status(400).json({ error: 'No file uploaded' });
    }
    
    const { originalname, mimetype, size, path: filePath } = req.file;
    const userId = req.user ? req.user.id : null;
    
    // Get file type from mimetype or extension
    let fileType = mimetype.split('/')[1];
    if (!fileType) {
      const extension = path.extname(originalname).toLowerCase();
      fileType = extension.slice(1) || 'unknown';
    }
    
    // Create file record in database
    const fileId = uuidv4();
    const file = await fileService.createFile(pool, {
      id: fileId,
      user_id: userId,
      filename: originalname,
      filepath: filePath,
      filetype: fileType,
      filesize: size
    });
    
    res.status(201).json({
      message: 'File uploaded successfully',
      file_id: fileId,
      filename: originalname,
      filetype: fileType,
      filesize: size
    });
  } catch (error) {
    logger.error('Error uploading file', { error });
    next(error);
  }
};

/**
 * Get all files
 */
const getFiles = (pool, logger) => async (req, res, next) => {
  try {
    const userId = req.user ? req.user.id : null;
    const files = await fileService.getFiles(pool, userId);
    res.json(files);
  } catch (error) {
    logger.error('Error getting files', { error });
    next(error);
  }
};

/**
 * Get a specific file by ID
 */
const getFileById = (pool, logger) => async (req, res, next) => {
  try {
    const { id } = req.params;
    const file = await fileService.getFileById(pool, id);
    
    if (!file) {
      return res.status(404).json({ error: 'File not found' });
    }
    
    res.json(file);
  } catch (error) {
    logger.error('Error getting file', { error });
    next(error);
  }
};

/**
 * Download a file
 */
const downloadFile = (pool, logger) => async (req, res, next) => {
  try {
    const { id } = req.params;
    const file = await fileService.getFileById(pool, id);
    
    if (!file) {
      return res.status(404).json({ error: 'File not found' });
    }
    
    // Check if file exists on disk
    if (!fs.existsSync(file.filepath)) {
      return res.status(404).json({ error: 'File not found on disk' });
    }
    
    res.download(file.filepath, file.filename, (err) => {
      if (err) {
        logger.error('Error downloading file', { error: err });
        return res.status(500).json({ error: 'File download failed' });
      }
    });
  } catch (error) {
    logger.error('Error downloading file', { error });
    next(error);
  }
};

/**
 * Delete a file
 */
const deleteFile = (pool, logger) => async (req, res, next) => {
  try {
    const { id } = req.params;
    const file = await fileService.getFileById(pool, id);
    
    if (!file) {
      return res.status(404).json({ error: 'File not found' });
    }
    
    // Delete file from disk
    if (fs.existsSync(file.filepath)) {
      fs.unlinkSync(file.filepath);
    }
    
    // Delete file record from database
    await fileService.deleteFile(pool, id);
    
    res.json({ message: 'File deleted successfully' });
  } catch (error) {
    logger.error('Error deleting file', { error });
    next(error);
  }
};

module.exports = {
  uploadFile,
  getFiles,
  getFileById,
  downloadFile,
  deleteFile
};
