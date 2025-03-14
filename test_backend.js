/**
 * Test script for the backend API
 * Validates that routes, controllers, and services are correctly implemented
 */

// Mock Database connection
// This prevents the tests from requiring an actual database
const mockDB = {
  query: jest.fn().mockResolvedValue({
    rows: [{ id: 1, name: 'Test' }],
    rowCount: 1
  })
};

// Mock services
jest.mock('./scheduling-platform/backend/src/services/optimizationService', () => ({
  createJob: jest.fn().mockResolvedValue({ id: 'job123', status: 'pending' }),
  getJobStatus: jest.fn().mockResolvedValue({ id: 'job123', status: 'completed' }),
  getJobs: jest.fn().mockResolvedValue([{ id: 'job123', status: 'completed' }])
}));

jest.mock('./scheduling-platform/backend/src/services/fileService', () => ({
  uploadFile: jest.fn().mockResolvedValue({ id: 'file123', filename: 'test.csv' }),
  getFileById: jest.fn().mockResolvedValue({ id: 'file123', filename: 'test.csv', data: 'test data' })
}));

jest.mock('./scheduling-platform/backend/src/services/userService', () => ({
  createUser: jest.fn().mockResolvedValue({ id: 'user123', email: 'test@example.com' }),
  loginUser: jest.fn().mockResolvedValue({ token: 'jwt123' }),
  getUserById: jest.fn().mockResolvedValue({ id: 'user123', email: 'test@example.com' })
}));

jest.mock('./scheduling-platform/backend/src/services/scheduleService', () => ({
  getSchedules: jest.fn().mockResolvedValue([{ id: 'schedule123', name: 'Test Schedule' }]),
  createSchedule: jest.fn().mockResolvedValue({ id: 'schedule123', name: 'Test Schedule' }),
  getScheduleById: jest.fn().mockResolvedValue({ id: 'schedule123', name: 'Test Schedule' })
}));

// Import SuperTest and Express app
const request = require('supertest');
const app = require('./scheduling-platform/backend/src/index');

// Test cases
describe('Backend API', () => {
  // Optimization Routes
  describe('Optimization Routes', () => {
    it('POST /api/optimization/jobs - Creates a new optimization job', async () => {
      const response = await request(app)
        .post('/api/optimization/jobs')
        .set('Authorization', 'Bearer test-token')
        .send({
          name: 'Test Job',
          algorithm: 'greedy',
          inputFiles: ['file123']
        });
      
      expect(response.status).toBe(201);
      expect(response.body).toHaveProperty('id', 'job123');
    });

    it('GET /api/optimization/jobs/:id - Gets job status', async () => {
      const response = await request(app)
        .get('/api/optimization/jobs/job123')
        .set('Authorization', 'Bearer test-token');
      
      expect(response.status).toBe(200);
      expect(response.body).toHaveProperty('status', 'completed');
    });
  });

  // File Routes
  describe('File Routes', () => {
    it('POST /api/files - Uploads a file', async () => {
      const response = await request(app)
        .post('/api/files')
        .set('Authorization', 'Bearer test-token')
        .attach('file', Buffer.from('test data'), 'test.csv');
      
      expect(response.status).toBe(201);
      expect(response.body).toHaveProperty('id', 'file123');
    });

    it('GET /api/files/:id - Gets file by ID', async () => {
      const response = await request(app)
        .get('/api/files/file123')
        .set('Authorization', 'Bearer test-token');
      
      expect(response.status).toBe(200);
      expect(response.body).toHaveProperty('filename', 'test.csv');
    });
  });

  // User Routes
  describe('User Routes', () => {
    it('POST /api/users/register - Registers a new user', async () => {
      const response = await request(app)
        .post('/api/users/register')
        .send({
          email: 'test@example.com',
          password: 'password123',
          firstName: 'Test',
          lastName: 'User'
        });
      
      expect(response.status).toBe(201);
      expect(response.body).toHaveProperty('id', 'user123');
    });

    it('POST /api/users/login - Logs in a user', async () => {
      const response = await request(app)
        .post('/api/users/login')
        .send({
          email: 'test@example.com',
          password: 'password123'
        });
      
      expect(response.status).toBe(200);
      expect(response.body).toHaveProperty('token', 'jwt123');
    });
  });

  // Schedule Routes
  describe('Schedule Routes', () => {
    it('GET /api/schedules - Gets all schedules', async () => {
      const response = await request(app)
        .get('/api/schedules')
        .set('Authorization', 'Bearer test-token');
      
      expect(response.status).toBe(200);
      expect(response.body).toBeInstanceOf(Array);
      expect(response.body.length).toBe(1);
    });

    it('POST /api/schedules - Creates a new schedule', async () => {
      const response = await request(app)
        .post('/api/schedules')
        .set('Authorization', 'Bearer test-token')
        .send({
          name: 'Test Schedule',
          jobId: 'job123'
        });
      
      expect(response.status).toBe(201);
      expect(response.body).toHaveProperty('id', 'schedule123');
    });

    it('GET /api/schedules/:id - Gets schedule by ID', async () => {
      const response = await request(app)
        .get('/api/schedules/schedule123')
        .set('Authorization', 'Bearer test-token');
      
      expect(response.status).toBe(200);
      expect(response.body).toHaveProperty('name', 'Test Schedule');
    });
  });
});