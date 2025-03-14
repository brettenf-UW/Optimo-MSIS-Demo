/**
 * Main entry point for the scheduling platform backend API server.
 */
const express = require('express');
const cors = require('cors');
const morgan = require('morgan');
const dotenv = require('dotenv');
const { Pool } = require('pg');
const winston = require('winston');

// Load environment variables
dotenv.config();

// Configure logger
const logger = winston.createLogger({
  level: process.env.LOG_LEVEL || 'info',
  format: winston.format.combine(
    winston.format.timestamp(),
    winston.format.json()
  ),
  transports: [
    new winston.transports.Console(),
    new winston.transports.File({ filename: 'logs/error.log', level: 'error' }),
    new winston.transports.File({ filename: 'logs/combined.log' })
  ]
});

// Initialize Express app
const app = express();
const port = process.env.PORT || 3000;

// Configure middleware
app.use(cors());
app.use(express.json());
app.use(express.urlencoded({ extended: true }));
app.use(morgan('combined'));

// Create PostgreSQL connection pool
const pool = new Pool({
  host: process.env.DB_HOST || 'localhost',
  port: process.env.DB_PORT || 5432,
  database: process.env.DB_NAME || 'scheduling',
  user: process.env.DB_USER || 'postgres',
  password: process.env.DB_PASSWORD || 'postgres'
});

// Health check endpoint
app.get('/api/health', (req, res) => {
  res.json({
    status: 'healthy',
    timestamp: new Date().toISOString()
  });
});

// Import routes
const optimizationRoutes = require('./routes/optimization');
const fileRoutes = require('./routes/files');
const userRoutes = require('./routes/users');
const scheduleRoutes = require('./routes/schedules');

// Register routes
app.use('/api/optimization', optimizationRoutes(pool, logger));
app.use('/api/files', fileRoutes(pool, logger));
app.use('/api/users', userRoutes(pool, logger));
app.use('/api/schedules', scheduleRoutes(pool, logger));

// Error handling middleware
app.use((err, req, res, next) => {
  logger.error(`Error: ${err.message}`, { error: err });
  res.status(err.status || 500).json({
    error: {
      message: err.message,
      status: err.status || 500
    }
  });
});

// Start the server
app.listen(port, () => {
  logger.info(`Server running on port ${port}`);
  console.log(`Server running on port ${port}`);
});

// Export app for testing
module.exports = app;