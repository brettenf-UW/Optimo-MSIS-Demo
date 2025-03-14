/**
 * Routes for schedule operations.
 */
const express = require('express');
const {
  getSchedules,
  getScheduleById,
  createSchedule,
  updateSchedule,
  deleteSchedule,
  exportSchedule
} = require('../controllers/scheduleController');
const { authenticate } = require('../middleware/auth');

module.exports = (pool, logger) => {
  const router = express.Router();

  /**
   * @route GET /api/schedules
   * @description Get all schedules
   * @access Private
   */
  router.get('/', authenticate, getSchedules(pool, logger));

  /**
   * @route GET /api/schedules/:id
   * @description Get a specific schedule by ID
   * @access Private
   */
  router.get('/:id', authenticate, getScheduleById(pool, logger));

  /**
   * @route POST /api/schedules
   * @description Create a new schedule
   * @access Private
   */
  router.post('/', authenticate, createSchedule(pool, logger));

  /**
   * @route PUT /api/schedules/:id
   * @description Update a schedule
   * @access Private
   */
  router.put('/:id', authenticate, updateSchedule(pool, logger));

  /**
   * @route DELETE /api/schedules/:id
   * @description Delete a schedule
   * @access Private
   */
  router.delete('/:id', authenticate, deleteSchedule(pool, logger));

  /**
   * @route GET /api/schedules/:id/export
   * @description Export a schedule as CSV
   * @access Private
   */
  router.get('/:id/export', authenticate, exportSchedule(pool, logger));

  return router;
};
