/**
 * Service for optimization operations.
 */
const axios = require('axios');
const FormData = require('form-data');
const fs = require('fs');
const { ApiError } = require('../utils/errorHandler');

// Configure optimizer API URL from environment variable
const OPTIMIZER_API_URL = process.env.OPTIMIZER_API_URL || 'http://optimizer:5000/api/v1';

/**
 * Create a new optimization job in the database
 */
const createJob = async (pool, jobData) => {
  const { id, algorithm, input_files, user_id, status } = jobData;
  
  try {
    const result = await pool.query(
      `INSERT INTO optimization_jobs 
        (id, algorithm, parameters, user_id, status, created_at) 
      VALUES 
        ($1, $2, $3, $4, $5, NOW()) 
      RETURNING *`,
      [id, algorithm, { input_files }, user_id, status]
    );
    
    return result.rows[0];
  } catch (error) {
    throw new ApiError(`Failed to create optimization job: ${error.message}`, 500);
  }
};

/**
 * Submit job to the optimizer service
 */
const submitJobToOptimizer = async (job) => {
  try {
    // Create form data for file upload
    const formData = new FormData();
    
    // Add algorithm parameter
    formData.append('algorithm', job.algorithm);
    
    // Add input files
    for (const fileInfo of job.parameters.input_files) {
      const fileContent = fs.createReadStream(fileInfo.path);
      formData.append('files', fileContent, fileInfo.name);
    }
    
    // Send request to optimizer API
    const response = await axios.post(
      `${OPTIMIZER_API_URL}/optimize`,
      formData,
      {
        headers: {
          ...formData.getHeaders(),
        },
        timeout: 30000 // 30 seconds timeout
      }
    );
    
    // Return job ID from optimizer
    return {
      job_id: response.data.job_id,
      status: response.data.status
    };
  } catch (error) {
    console.error('Error submitting job to optimizer:', error);
    throw new ApiError(`Failed to submit job to optimizer: ${error.message}`, 500);
  }
};

/**
 * Check job status with the optimizer service
 */
const checkJobStatus = async (optimizerJobId) => {
  try {
    const response = await axios.get(`${OPTIMIZER_API_URL}/jobs/${optimizerJobId}`);
    return {
      status: response.data.status,
      result: response.data.results || null,
      error: response.data.error || null
    };
  } catch (error) {
    console.error('Error checking job status with optimizer:', error);
    throw new ApiError(`Failed to check job status: ${error.message}`, 500);
  }
};

/**
 * Update job status in the database
 */
const updateJobStatus = async (pool, jobId, status, additionalData = {}) => {
  try {
    const updateFields = ['status = $1'];
    const updateValues = [status];
    let valueIndex = 2;
    
    if (additionalData.optimizer_job_id) {
      updateFields.push(`optimizer_job_id = $${valueIndex}`);
      updateValues.push(additionalData.optimizer_job_id);
      valueIndex++;
    }
    
    if (additionalData.result) {
      updateFields.push(`result = $${valueIndex}`);
      updateValues.push(JSON.stringify(additionalData.result));
      valueIndex++;
    }
    
    if (additionalData.error) {
      updateFields.push(`error_message = $${valueIndex}`);
      updateValues.push(additionalData.error);
      valueIndex++;
    }
    
    if (status === 'completed' || status === 'failed') {
      updateFields.push(`completed_at = NOW()`);
    } else if (status === 'processing') {
      updateFields.push(`started_at = NOW()`);
    }
    
    updateFields.push(`updated_at = NOW()`);
    
    updateValues.push(jobId);
    
    const result = await pool.query(
      `UPDATE optimization_jobs
      SET ${updateFields.join(', ')}
      WHERE id = $${valueIndex}
      RETURNING *`,
      updateValues
    );
    
    if (result.rows.length === 0) {
      throw new ApiError(`Job not found: ${jobId}`, 404);
    }
    
    return result.rows[0];
  } catch (error) {
    console.error('Error updating job status:', error);
    throw new ApiError(`Failed to update job status: ${error.message}`, 500);
  }
};

/**
 * Get all optimization jobs from the database
 */
const getJobs = async (pool, userId = null) => {
  try {
    let query = `
      SELECT * FROM optimization_jobs
      ORDER BY created_at DESC
    `;
    
    let queryParams = [];
    
    if (userId) {
      query = `
        SELECT * FROM optimization_jobs
        WHERE user_id = $1
        ORDER BY created_at DESC
      `;
      queryParams = [userId];
    }
    
    const result = await pool.query(query, queryParams);
    return result.rows;
  } catch (error) {
    throw new ApiError(`Failed to get optimization jobs: ${error.message}`, 500);
  }
};

/**
 * Get a specific optimization job by ID
 */
const getJobById = async (pool, jobId) => {
  try {
    const result = await pool.query(
      'SELECT * FROM optimization_jobs WHERE id = $1',
      [jobId]
    );
    
    if (result.rows.length === 0) {
      return null;
    }
    
    return result.rows[0];
  } catch (error) {
    throw new ApiError(`Failed to get optimization job: ${error.message}`, 500);
  }
};

/**
 * Delete job from the optimizer service
 */
const deleteOptimizerJob = async (optimizerJobId) => {
  try {
    await axios.delete(`${OPTIMIZER_API_URL}/jobs/${optimizerJobId}`);
    return true;
  } catch (error) {
    console.error('Error deleting job from optimizer:', error);
    throw new ApiError(`Failed to delete job from optimizer: ${error.message}`, 500);
  }
};

/**
 * Delete an optimization job from the database
 */
const deleteJob = async (pool, jobId) => {
  try {
    const result = await pool.query(
      'DELETE FROM optimization_jobs WHERE id = $1 RETURNING *',
      [jobId]
    );
    
    if (result.rows.length === 0) {
      throw new ApiError(`Job not found: ${jobId}`, 404);
    }
    
    return result.rows[0];
  } catch (error) {
    throw new ApiError(`Failed to delete optimization job: ${error.message}`, 500);
  }
};

/**
 * Download job results from the optimizer service
 */
const downloadJobResults = async (optimizerJobId, fileType) => {
  try {
    const response = await axios.get(
      `${OPTIMIZER_API_URL}/jobs/${optimizerJobId}/download/${fileType}`,
      { responseType: 'stream' }
    );
    
    return response;
  } catch (error) {
    console.error('Error downloading job results from optimizer:', error);
    throw new ApiError(`Failed to download job results: ${error.message}`, 500);
  }
};

module.exports = {
  createJob,
  submitJobToOptimizer,
  checkJobStatus,
  updateJobStatus,
  getJobs,
  getJobById,
  deleteOptimizerJob,
  deleteJob,
  downloadJobResults
};