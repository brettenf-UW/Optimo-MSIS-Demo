/**
 * Service for schedule operations.
 */
const { ApiError } = require('../utils/errorHandler');

/**
 * Create a new schedule in the database
 */
const createSchedule = async (pool, scheduleData) => {
  const { name, description, user_id } = scheduleData;
  
  try {
    const result = await pool.query(
      `INSERT INTO schedules
        (name, description, user_id, created_at, updated_at)
      VALUES
        ($1, $2, $3, NOW(), NOW())
      RETURNING *`,
      [name, description || null, user_id]
    );
    
    return result.rows[0];
  } catch (error) {
    throw new ApiError(`Failed to create schedule: ${error.message}`, 500);
  }
};

/**
 * Get all schedules
 */
const getAllSchedules = async (pool) => {
  try {
    const result = await pool.query(
      `SELECT s.*, u.username as created_by,
        (SELECT COUNT(*) FROM schedule_sections WHERE schedule_id = s.id) as section_count,
        (SELECT COUNT(*) FROM schedule_assignments WHERE schedule_id = s.id) as assignment_count
      FROM schedules s
      LEFT JOIN users u ON s.user_id = u.id
      ORDER BY s.created_at DESC`
    );
    
    return result.rows;
  } catch (error) {
    throw new ApiError(`Failed to get schedules: ${error.message}`, 500);
  }
};

/**
 * Get schedules by user
 */
const getUserSchedules = async (pool, userId) => {
  try {
    const result = await pool.query(
      `SELECT s.*, u.username as created_by,
        (SELECT COUNT(*) FROM schedule_sections WHERE schedule_id = s.id) as section_count,
        (SELECT COUNT(*) FROM schedule_assignments WHERE schedule_id = s.id) as assignment_count
      FROM schedules s
      LEFT JOIN users u ON s.user_id = u.id
      WHERE s.user_id = $1
      ORDER BY s.created_at DESC`,
      [userId]
    );
    
    return result.rows;
  } catch (error) {
    throw new ApiError(`Failed to get user schedules: ${error.message}`, 500);
  }
};

/**
 * Get a schedule by ID
 */
const getScheduleById = async (pool, scheduleId) => {
  try {
    const result = await pool.query(
      `SELECT s.*, u.username as created_by
      FROM schedules s
      LEFT JOIN users u ON s.user_id = u.id
      WHERE s.id = $1`,
      [scheduleId]
    );
    
    if (result.rows.length === 0) {
      return null;
    }
    
    return result.rows[0];
  } catch (error) {
    throw new ApiError(`Failed to get schedule: ${error.message}`, 500);
  }
};

/**
 * Update a schedule
 */
const updateSchedule = async (pool, scheduleId, updates) => {
  try {
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
    
    // Add schedule ID to parameters
    updateValues.push(scheduleId);
    
    const query = `
      UPDATE schedules
      SET ${updateFields.join(', ')}
      WHERE id = $${valueIndex}
      RETURNING *
    `;
    
    const result = await pool.query(query, updateValues);
    
    if (result.rows.length === 0) {
      throw new ApiError(`Schedule not found: ${scheduleId}`, 404);
    }
    
    return result.rows[0];
  } catch (error) {
    if (error instanceof ApiError) {
      throw error;
    }
    
    throw new ApiError(`Failed to update schedule: ${error.message}`, 500);
  }
};

/**
 * Delete a schedule and all associated sections and assignments
 */
const deleteSchedule = async (pool, scheduleId) => {
  try {
    // Use a transaction to ensure all deletes are atomic
    await pool.query('BEGIN');
    
    // Delete assignments first (child records)
    await pool.query(
      'DELETE FROM schedule_assignments WHERE schedule_id = $1',
      [scheduleId]
    );
    
    // Delete sections
    await pool.query(
      'DELETE FROM schedule_sections WHERE schedule_id = $1',
      [scheduleId]
    );
    
    // Delete schedule
    const result = await pool.query(
      'DELETE FROM schedules WHERE id = $1 RETURNING id',
      [scheduleId]
    );
    
    if (result.rows.length === 0) {
      await pool.query('ROLLBACK');
      throw new ApiError(`Schedule not found: ${scheduleId}`, 404);
    }
    
    await pool.query('COMMIT');
    
    return true;
  } catch (error) {
    await pool.query('ROLLBACK');
    
    if (error instanceof ApiError) {
      throw error;
    }
    
    throw new ApiError(`Failed to delete schedule: ${error.message}`, 500);
  }
};

/**
 * Get sections for a schedule
 */
const getScheduleSections = async (pool, scheduleId) => {
  try {
    const result = await pool.query(
      `SELECT * FROM schedule_sections
      WHERE schedule_id = $1
      ORDER BY section_id`,
      [scheduleId]
    );
    
    return result.rows;
  } catch (error) {
    throw new ApiError(`Failed to get schedule sections: ${error.message}`, 500);
  }
};

/**
 * Add sections to a schedule
 */
const addSectionsToSchedule = async (pool, scheduleId, sections) => {
  try {
    // Use a transaction for batch inserts
    await pool.query('BEGIN');
    
    for (const section of sections) {
      await pool.query(
        `INSERT INTO schedule_sections
          (schedule_id, section_id, course_id, teacher_id, period_id, capacity, room)
        VALUES
          ($1, $2, $3, $4, $5, $6, $7)`,
        [
          scheduleId,
          section.section_id,
          section.course_id,
          section.teacher_id || null,
          section.period_id || null,
          section.capacity || 30,
          section.room || null
        ]
      );
    }
    
    await pool.query('COMMIT');
    
    return true;
  } catch (error) {
    await pool.query('ROLLBACK');
    throw new ApiError(`Failed to add sections to schedule: ${error.message}`, 500);
  }
};

/**
 * Update sections in a schedule
 */
const updateScheduleSections = async (pool, scheduleId, sections) => {
  try {
    // Use a transaction
    await pool.query('BEGIN');
    
    // Delete existing sections
    await pool.query(
      'DELETE FROM schedule_sections WHERE schedule_id = $1',
      [scheduleId]
    );
    
    // Add new sections
    await addSectionsToSchedule(pool, scheduleId, sections);
    
    await pool.query('COMMIT');
    
    return true;
  } catch (error) {
    await pool.query('ROLLBACK');
    throw new ApiError(`Failed to update schedule sections: ${error.message}`, 500);
  }
};

/**
 * Get assignments for a schedule
 */
const getScheduleAssignments = async (pool, scheduleId) => {
  try {
    const result = await pool.query(
      `SELECT * FROM schedule_assignments
      WHERE schedule_id = $1
      ORDER BY student_id, section_id`,
      [scheduleId]
    );
    
    return result.rows;
  } catch (error) {
    throw new ApiError(`Failed to get schedule assignments: ${error.message}`, 500);
  }
};

/**
 * Add assignments to a schedule
 */
const addAssignmentsToSchedule = async (pool, scheduleId, assignments) => {
  try {
    // Use a transaction for batch inserts
    await pool.query('BEGIN');
    
    for (const assignment of assignments) {
      await pool.query(
        `INSERT INTO schedule_assignments
          (schedule_id, student_id, section_id)
        VALUES
          ($1, $2, $3)`,
        [
          scheduleId,
          assignment.student_id,
          assignment.section_id
        ]
      );
    }
    
    await pool.query('COMMIT');
    
    return true;
  } catch (error) {
    await pool.query('ROLLBACK');
    throw new ApiError(`Failed to add assignments to schedule: ${error.message}`, 500);
  }
};

/**
 * Update assignments in a schedule
 */
const updateScheduleAssignments = async (pool, scheduleId, assignments) => {
  try {
    // Use a transaction
    await pool.query('BEGIN');
    
    // Delete existing assignments
    await pool.query(
      'DELETE FROM schedule_assignments WHERE schedule_id = $1',
      [scheduleId]
    );
    
    // Add new assignments
    if (assignments.length > 0) {
      await addAssignmentsToSchedule(pool, scheduleId, assignments);
    }
    
    await pool.query('COMMIT');
    
    return true;
  } catch (error) {
    await pool.query('ROLLBACK');
    throw new ApiError(`Failed to update schedule assignments: ${error.message}`, 500);
  }
};

module.exports = {
  createSchedule,
  getAllSchedules,
  getUserSchedules,
  getScheduleById,
  updateSchedule,
  deleteSchedule,
  getScheduleSections,
  addSectionsToSchedule,
  updateScheduleSections,
  getScheduleAssignments,
  addAssignmentsToSchedule,
  updateScheduleAssignments
};