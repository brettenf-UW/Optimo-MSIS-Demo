/**
 * Controllers for optimization operations.
 */
const axios = require('axios');
const { v4: uuidv4 } = require('uuid');
const optimizationService = require('../services/optimizationService');

/**
 * Create a new optimization job
 */
const createJob = (pool, logger) => async (req, res, next) => {
  try {
    const { algorithm, input_files } = req.body;
    
    if (!algorithm || !input_files || !Array.isArray(input_files)) {
      return res.status(400).json({ error: 'Algorithm and input files are required' });
    }
    
    // Create job record
    const jobId = uuidv4();
    const userId = req.user ? req.user.id : null;
    
    const job = await optimizationService.createJob(pool, {
      id: jobId,
      algorithm,
      input_files,
      user_id: userId,
      status: 'pending'
    });
    
    // Submit job to optimizer service
    const optimizerResponse = await optimizationService.submitJobToOptimizer(job);
    
    // Update job with optimizer response
    await optimizationService.updateJobStatus(pool, jobId, 'processing', {
      optimizer_job_id: optimizerResponse.job_id
    });
    
    res.status(201).json({
      message: 'Optimization job created successfully',
      job_id: jobId,
      optimizer_job_id: optimizerResponse.job_id,
      status: 'processing'
    });
  } catch (error) {
    logger.error('Error creating optimization job', { error });
    next(error);
  }
};

/**
 * Get all optimization jobs
 */
const getJobs = (pool, logger) => async (req, res, next) => {
  try {
    const userId = req.user ? req.user.id : null;
    const jobs = await optimizationService.getJobs(pool, userId);
    res.json(jobs);
  } catch (error) {
    logger.error('Error getting optimization jobs', { error });
    next(error);
  }
};

/**
 * Get a specific optimization job by ID
 */
const getJobById = (pool, logger) => async (req, res, next) => {
  try {
    const { id } = req.params;
    const job = await optimizationService.getJobById(pool, id);
    
    if (!job) {
      return res.status(404).json({ error: 'Job not found' });
    }
    
    // If job is still processing, check status with optimizer service
    if (job.status === 'processing' && job.optimizer_job_id) {
      try {
        const optimizerStatus = await optimizationService.checkJobStatus(job.optimizer_job_id);
        
        // Update job status if changed
        if (optimizerStatus.status !== job.status) {
          await optimizationService.updateJobStatus(pool, id, optimizerStatus.status, {
            result: optimizerStatus.result,
            error: optimizerStatus.error
          });
          job.status = optimizerStatus.status;
          job.result = optimizerStatus.result;
          job.error = optimizerStatus.error;
        }
      } catch (error) {
        logger.warn('Failed to check optimizer service status', { error });
        // Continue with existing job information
      }
    }
    
    res.json(job);
  } catch (error) {
    logger.error('Error getting optimization job', { error });
    next(error);
  }
};

/**
 * Delete an optimization job
 */
const deleteJob = (pool, logger) => async (req, res, next) => {
  try {
    const { id } = req.params;
    const job = await optimizationService.getJobById(pool, id);
    
    if (!job) {
      return res.status(404).json({ error: 'Job not found' });
    }
    
    // Delete job from database
    await optimizationService.deleteJob(pool, id);
    
    // Try to delete job from optimizer service if it exists
    if (job.optimizer_job_id) {
      try {
        await optimizationService.deleteOptimizerJob(job.optimizer_job_id);
      } catch (error) {
        logger.warn('Failed to delete job from optimizer service', { error });
        // Continue anyway - the job was deleted from our database
      }
    }
    
    res.json({ message: 'Job deleted successfully' });
  } catch (error) {
    logger.error('Error deleting optimization job', { error });
    next(error);
  }
};

module.exports = {
  createJob,
  getJobs,
  getJobById,
  deleteJob
};
