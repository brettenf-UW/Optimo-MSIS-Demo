/**
 * Controllers for schedule operations.
 */
const { Parser } = require('json2csv');
const scheduleService = require('../services/scheduleService');

/**
 * Get all schedules
 */
const getSchedules = (pool, logger) => async (req, res, next) => {
  try {
    const userId = req.user.id;
    const role = req.user.role;
    
    // Admins can see all schedules, users can only see their own
    const schedules = role === 'admin' 
      ? await scheduleService.getAllSchedules(pool)
      : await scheduleService.getUserSchedules(pool, userId);
    
    res.json(schedules);
  } catch (error) {
    logger.error('Error getting schedules', { error });
    next(error);
  }
};

/**
 * Get a specific schedule by ID
 */
const getScheduleById = (pool, logger) => async (req, res, next) => {
  try {
    const { id } = req.params;
    const userId = req.user.id;
    const role = req.user.role;
    
    const schedule = await scheduleService.getScheduleById(pool, id);
    
    if (!schedule) {
      return res.status(404).json({ error: 'Schedule not found' });
    }
    
    // Check user has permission to view this schedule
    if (role !== 'admin' && schedule.user_id !== userId) {
      return res.status(403).json({ error: 'Not authorized to view this schedule' });
    }
    
    // Get all related data for the schedule
    const sections = await scheduleService.getScheduleSections(pool, id);
    const assignments = await scheduleService.getScheduleAssignments(pool, id);
    
    res.json({
      ...schedule,
      sections,
      assignments
    });
  } catch (error) {
    logger.error('Error getting schedule', { error });
    next(error);
  }
};

/**
 * Create a new schedule
 */
const createSchedule = (pool, logger) => async (req, res, next) => {
  try {
    const { name, description, sections, assignments } = req.body;
    const userId = req.user.id;
    
    if (!name || !sections || !Array.isArray(sections)) {
      return res.status(400).json({ error: 'Name and sections array are required' });
    }
    
    // Create the schedule
    const schedule = await scheduleService.createSchedule(pool, {
      name,
      description,
      user_id: userId
    });
    
    // Add sections to the schedule
    await scheduleService.addSectionsToSchedule(pool, schedule.id, sections);
    
    // Add assignments if provided
    if (assignments && Array.isArray(assignments)) {
      await scheduleService.addAssignmentsToSchedule(pool, schedule.id, assignments);
    }
    
    res.status(201).json({
      message: 'Schedule created successfully',
      schedule_id: schedule.id,
      name: schedule.name
    });
  } catch (error) {
    logger.error('Error creating schedule', { error });
    next(error);
  }
};

/**
 * Update a schedule
 */
const updateSchedule = (pool, logger) => async (req, res, next) => {
  try {
    const { id } = req.params;
    const { name, description, sections, assignments } = req.body;
    const userId = req.user.id;
    const role = req.user.role;
    
    // Get existing schedule
    const existingSchedule = await scheduleService.getScheduleById(pool, id);
    
    if (!existingSchedule) {
      return res.status(404).json({ error: 'Schedule not found' });
    }
    
    // Check user has permission to update this schedule
    if (role !== 'admin' && existingSchedule.user_id !== userId) {
      return res.status(403).json({ error: 'Not authorized to update this schedule' });
    }
    
    // Update schedule metadata
    const updates = {};
    if (name) updates.name = name;
    if (description !== undefined) updates.description = description;
    
    if (Object.keys(updates).length > 0) {
      await scheduleService.updateSchedule(pool, id, updates);
    }
    
    // Update sections if provided
    if (sections && Array.isArray(sections)) {
      await scheduleService.updateScheduleSections(pool, id, sections);
    }
    
    // Update assignments if provided
    if (assignments && Array.isArray(assignments)) {
      await scheduleService.updateScheduleAssignments(pool, id, assignments);
    }
    
    res.json({ message: 'Schedule updated successfully' });
  } catch (error) {
    logger.error('Error updating schedule', { error });
    next(error);
  }
};

/**
 * Delete a schedule
 */
const deleteSchedule = (pool, logger) => async (req, res, next) => {
  try {
    const { id } = req.params;
    const userId = req.user.id;
    const role = req.user.role;
    
    // Get existing schedule
    const existingSchedule = await scheduleService.getScheduleById(pool, id);
    
    if (!existingSchedule) {
      return res.status(404).json({ error: 'Schedule not found' });
    }
    
    // Check user has permission to delete this schedule
    if (role !== 'admin' && existingSchedule.user_id !== userId) {
      return res.status(403).json({ error: 'Not authorized to delete this schedule' });
    }
    
    // Delete schedule and all related data
    await scheduleService.deleteSchedule(pool, id);
    
    res.json({ message: 'Schedule deleted successfully' });
  } catch (error) {
    logger.error('Error deleting schedule', { error });
    next(error);
  }
};

/**
 * Export a schedule as CSV
 */
const exportSchedule = (pool, logger) => async (req, res, next) => {
  try {
    const { id } = req.params;
    const userId = req.user.id;
    const role = req.user.role;
    
    // Get existing schedule
    const schedule = await scheduleService.getScheduleById(pool, id);
    
    if (!schedule) {
      return res.status(404).json({ error: 'Schedule not found' });
    }
    
    // Check user has permission to export this schedule
    if (role !== 'admin' && schedule.user_id !== userId) {
      return res.status(403).json({ error: 'Not authorized to export this schedule' });
    }
    
    // Get sections and assignments for the schedule
    const sections = await scheduleService.getScheduleSections(pool, id);
    const assignments = await scheduleService.getScheduleAssignments(pool, id);
    
    // Generate master schedule CSV
    const masterScheduleFields = ['section_id', 'course_id', 'teacher_id', 'period_id', 'room', 'capacity'];
    const masterScheduleParser = new Parser({ fields: masterScheduleFields });
    const masterScheduleCsv = masterScheduleParser.parse(sections);
    
    // Generate student assignments CSV
    const assignmentsFields = ['student_id', 'section_id'];
    const assignmentsParser = new Parser({ fields: assignmentsFields });
    const assignmentsCsv = assignmentsParser.parse(assignments);
    
    // Set headers for download and send CSVs as attachment
    res.setHeader('Content-Type', 'application/zip');
    res.setHeader('Content-Disposition', `attachment; filename="schedule-${id}.zip"`);
    
    // Use JSZip to create a zip file with both CSVs
    const JSZip = require('jszip');
    const zip = new JSZip();
    
    zip.file('master_schedule.csv', masterScheduleCsv);
    zip.file('student_assignments.csv', assignmentsCsv);
    
    // Generate zip file and stream it to response
    zip
      .generateNodeStream({ type: 'nodebuffer', streamFiles: true })
      .pipe(res)
      .on('error', (err) => {
        logger.error('Error generating zip file', { error: err });
        res.status(500).json({ error: 'Error generating export file' });
      });
  } catch (error) {
    logger.error('Error exporting schedule', { error });
    next(error);
  }
};

module.exports = {
  getSchedules,
  getScheduleById,
  createSchedule,
  updateSchedule,
  deleteSchedule,
  exportSchedule
};
