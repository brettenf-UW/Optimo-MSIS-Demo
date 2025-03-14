/**
 * Routes for file operations.
 */
const express = require('express');
const multer = require('multer');
const { uploadFile, getFiles, getFileById, downloadFile, deleteFile } = require('../controllers/fileController');

// Configure multer for file uploads
const storage = multer.diskStorage({
  destination: (req, file, cb) => {
    cb(null, process.env.UPLOAD_DIR || 'uploads/');
  },
  filename: (req, file, cb) => {
    cb(null, `${Date.now()}-${file.originalname}`);
  }
});

const upload = multer({ storage });

module.exports = (pool, logger) => {
  const router = express.Router();

  /**
   * @route POST /api/files/upload
   * @description Upload a new file
   * @access Public
   */
  router.post('/upload', upload.single('file'), uploadFile(pool, logger));

  /**
   * @route GET /api/files
   * @description Get all files
   * @access Public
   */
  router.get('/', getFiles(pool, logger));

  /**
   * @route GET /api/files/:id
   * @description Get a specific file by ID
   * @access Public
   */
  router.get('/:id', getFileById(pool, logger));

  /**
   * @route GET /api/files/:id/download
   * @description Download a file
   * @access Public
   */
  router.get('/:id/download', downloadFile(pool, logger));

  /**
   * @route DELETE /api/files/:id
   * @description Delete a file
   * @access Public
   */
  router.delete('/:id', deleteFile(pool, logger));

  return router;
};
