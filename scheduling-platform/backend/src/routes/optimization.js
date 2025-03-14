/**
 * Routes for optimization operations.
 */
const express = require('express');
const { createJob, getJobById, getJobs, deleteJob } = require('../controllers/optimizationController');

module.exports = (pool, logger) => {
  const router = express.Router();

  /**
   * @route POST /api/optimization/jobs
   * @description Create a new optimization job
   * @access Public
   */
  router.post('/jobs', createJob(pool, logger));

  /**
   * @route GET /api/optimization/jobs
   * @description Get all optimization jobs
   * @access Public
   */
  router.get('/jobs', getJobs(pool, logger));

  /**
   * @route GET /api/optimization/jobs/:id
   * @description Get a specific optimization job by ID
   * @access Public
   */
  router.get('/jobs/:id', getJobById(pool, logger));

  /**
   * @route DELETE /api/optimization/jobs/:id
   * @description Delete an optimization job
   * @access Public
   */
  router.delete('/jobs/:id', deleteJob(pool, logger));

  return router;
};
