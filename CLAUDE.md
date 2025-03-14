# School Scheduling Platform

## Project Overview

This is a school scheduling optimization platform that runs on EC2 using Docker containers. The system uses Gurobi's optimization engine to generate efficient schedules for students, teachers, and classrooms based on various constraints.

## Common Commands

### Build & Run
```
docker-compose build         # Build all containers
docker-compose up -d         # Start all services in detached mode
docker-compose down          # Stop all services
```

### Testing
```
# Backend
cd backend && npm test                     # Run all backend tests
cd backend && npm test -- --grep "pattern" # Run specific backend tests
cd backend && npm run lint                 # Lint backend code
cd backend && npm run typecheck            # Run TypeScript type checking

# Frontend
cd frontend && npm test                    # Run all frontend tests
cd frontend && npm run test:watch          # Run tests in watch mode
cd frontend && npm run lint                # Lint frontend code

# Optimizer
cd optimizer && python -m pytest           # Run all optimizer tests
cd optimizer && python -m pytest tests/test_file.py::test_name  # Run specific test
```

## Code Style Guidelines

- **Naming**: Use camelCase for JavaScript/TypeScript, snake_case for Python
- **Imports**: Group imports (standard library, third-party, local) with blank line separators
- **Error Handling**: Use try/catch for async operations, proper logging with appropriate levels
- **React Components**: Functional components with hooks preferred over class components
- **Python**: Follow PEP 8 style guide with 4-space indentation
- **TypeScript**: Explicit return types on functions, interface over type where possible
- **Documentation**: JSDoc for JS/TS functions, docstrings for Python, update CHANGELOG.md

## System Architecture

The platform consists of several interconnected components:

- **Frontend**: React-based UI for uploading data, configuring optimization parameters, and viewing results
- **Backend API**: Node.js/Express server handling file management, database operations, and optimization requests
- **Optimizer Service**: Python container with Gurobi for running scheduling algorithms
- **Database**: PostgreSQL for storing metadata, job status, and references to files
- **Storage**: AWS S3 for persistent storage of input and output files
- **Admin Tools**: Adminer for database management

### Directory Structure

```
scheduling-platform/
├── docker/                      # Docker configuration files
├── backend/                     # Node.js API server
├── frontend/                    # React frontend application
├── optimizer/                   # Python optimization service
├── database/                    # Database initialization scripts
├── nginx/                       # Web server configuration
└── scripts/                     # Utility scripts for setup and deployment
```

## Setup and Installation

### Prerequisites

- AWS EC2 instance (recommended: t3.large or better with 16GB+ RAM)
- Docker and Docker Compose installed
- AWS S3 bucket for file storage
- Gurobi license file

### Installation Steps

1. Clone this repository to your EC2 instance
2. Place your Gurobi license file at `docker/gurobi.lic`
3. Create a `.env` file with necessary configuration variables
4. Start the database containers:
   ```
   docker-compose up -d postgres adminer
   ```
5. Initialize the database schema:
   - Access Adminer at http://[EC2-IP]:8080
   - Run the SQL from `database/init.sql`
6. Start the remaining containers:
   ```
   docker-compose up -d
   ```

## Using the Platform

### Scheduling Workflow

1. **Upload Input Files**:
   - Student information (CSV)
   - Teacher availability (CSV)
   - Course information (CSV)
   - Existing section information (CSV)
   - Period definitions (CSV)

2. **Configure Optimization Parameters**:
   - Set prioritization rules for scheduling
   - Define special constraints (e.g., course restrictions, room requirements)
   - Select optimization algorithm (Greedy or MILP)

3. **Run Optimization**:
   - Submit job through the UI
   - Monitor progress in real-time
   - Review initial results

4. **Download Results**:
   - Master schedule (sections to periods)
   - Student assignments
   - Teacher schedules
   - Constraint violations report

### Key Algorithms

The platform includes two main scheduling algorithms:

1. **Greedy Algorithm** (`optimizer/src/greedy.py`):
   - Fast initial scheduling
   - Used for generating initial solutions
   - Good for quick previews and testing

2. **Mixed Integer Linear Programming** (`optimizer/src/milp_soft.py`):
   - Optimal scheduling with soft constraints
   - Uses Gurobi solver for high-quality results
   - Handles complex constraints and priorities

## Development Guide

### Adding New Features

1. **Backend Changes**:
   - Add routes in `backend/src/routes/`
   - Implement controllers in `backend/src/controllers/`
   - Define models in `backend/src/models/`

2. **Frontend Updates**:
   - Add components in `frontend/src/components/`
   - Update pages in `frontend/src/pages/`
   - Extend API client in `frontend/src/services/`

3. **Optimizer Improvements**:
   - Modify algorithms in `optimizer/src/`
   - Update API endpoints in `optimizer/api.py`
   - Add new constraints or objective functions

### Testing Changes

1. Test backend APIs with Postman or similar tools
2. Run frontend tests with `npm test`
3. Validate optimization results with test datasets
4. Compare results against expected outcomes

## Troubleshooting

### Common Issues

- **Database Connection Errors**:
  - Check PostgreSQL container logs
  - Verify connection settings in `.env` file

- **Optimization Failures**:
  - Check Gurobi license validity
  - Examine optimizer container logs
  - Verify input data formats and values

- **Frontend Display Problems**:
  - Check browser console for errors
  - Verify API responses from backend

### Logging

- All containers log to Docker's logging system
- View logs with `docker logs [container-name]`
- Backend and optimizer have detailed logging for debugging

## Maintenance

### Backups

- Database: Use PostgreSQL's built-in backup tools
- S3 files: Enable versioning on your S3 bucket
- Configuration: Store `.env` securely

### Updates

- Pull latest code changes from repository
- Rebuild containers: `docker-compose build`
- Restart services: `docker-compose down && docker-compose up -d`

## Contributing

Please follow these guidelines when contributing to the project:

1. Create a feature branch for new work
2. Follow coding standards and conventions
3. Write tests for new functionality
4. Document changes in code and update this guide if needed
5. Submit pull requests for review

## License and Credits

- Scheduling algorithms: Copyright © Your Organization
- Gurobi Optimizer: Requires commercial license
- Additional open-source components: See respective license files