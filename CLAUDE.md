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

## Project Resources

### Test Input Files
A set of test CSV files is available in the `Test Input Files/` directory:
- `Period.csv` - Defines school periods
- `Sections_Information.csv` - Information about existing sections
- `Student_Info.csv` - Student demographics and records
- `Student_Preference_Info.csv` - Student course preferences
- `Teacher_Info.csv` - Teacher information
- `Teacher_unavailability.csv` - Teacher unavailability periods

These files should be used for testing the optimization algorithms and verifying system functionality.

### Legacy Optimization Files
Original optimization scripts are stored in the `Old Optimizaion files to build of of/` directory:
- `greedy.py` - Initial greedy algorithm implementation
- `load.py` - Data loading utilities
- `milp_soft.py` - Mixed Integer Linear Programming implementation
- `schedule_optimizer.py` - Main optimizer entry point

When implementing the new optimization service, incorporate these algorithms while adapting them to the new system architecture.

## System Architecture

The platform consists of several interconnected components:

- **Frontend**: React-based UI for uploading data, configuring optimization parameters, and viewing results
- **Backend API**: Node.js/Express server handling file management, database operations, and optimization requests
- **Optimizer Service**: Python container with Gurobi for running scheduling algorithms
- **Database**: PostgreSQL for storing metadata, job status, and references to files
- **Storage**: AWS S3 for persistent storage of input and output files
- **Admin Tools**: Adminer for database management

## Implementation Progress Notes

### Completed Components

#### Project Structure
- ✅ Created main project directory structure following the architecture above
- ✅ Set up Docker Compose configuration with services for all components
- ✅ Created Dockerfiles for backend, frontend, and optimizer services
- ✅ Implemented database initialization script with complete schema
  - Tables for users, courses, teachers, students, periods
  - Relationship tables for student preferences, teacher unavailability
  - Job tracking and file management tables

#### Implementation Details

The implementation follows a microservice architecture with three main components:

1. **Backend API Service**: Node.js/Express application
   - REST API endpoints for all platform features
   - JWT-based authentication and authorization
   - Connection to PostgreSQL database
   - Communication with the optimizer service

2. **Optimizer Service**: Python Flask application
   - Core scheduling algorithms implementation
   - Data loading and processing
   - REST API for job submission and status checking
   - Result generation and reporting

3. **Frontend Application**: React SPA (To be implemented)
   - User interface for all platform features
   - Communication with backend API
   - Interactive visualization of schedules
   - User authentication and management

#### Optimizer Service Implementation
- ✅ Created a well-structured Python package with clean architecture:
  - **Domain Layer**:
    - Entity classes (`src/models/entities.py`) for `Student`, `Teacher`, `Period`, `Section`, etc.
    - Rich domain models with behavior and relationships
  - **Data Layer**:
    - CSV loading and validation (`src/data/loader.py`)
    - Data format conversion (`src/data/converter.py`)
  - **Algorithm Layer**:
    - Greedy optimization algorithm (`src/algorithms/greedy.py`)
    - Future MILP algorithm support (`src/algorithms/milp.py`)
  - **Service Layer**:
    - Main optimization orchestration (`src/optimizer.py`)
  - **API Layer**:
    - REST API with Flask (`src/api.py`)
    - CLI interface (`src/cli.py`)
- ✅ Implemented data loading pipeline based on legacy code:
  - Robust CSV file parsing with error handling
  - Entity relationship validation
  - Multiple fallback options for missing data
  - Detailed logging for troubleshooting
- ✅ Developed greedy optimization algorithm with sophisticated features:
  - Section scheduling based on complex constraints and priorities
  - Student assignment accounting for preferences and requirements
  - Special handling for courses with specific period requirements
  - Balance optimization for student distribution
- ✅ Created dual interfaces for flexibility:
  - RESTful API for service integration using Flask
  - Command-line interface for batch processing
- ✅ Built testing infrastructure:
  - Unit tests for core components
  - Integration tests for end-to-end flows
  - Test data generation utilities

#### Backend API Implementation
- ✅ Established Express.js application with comprehensive architecture:
  - **Routing Layer**:
    - Optimization job endpoints (`src/routes/optimization.js`)
    - File management endpoints (`src/routes/files.js`)
    - User authentication endpoints (`src/routes/users.js`)
    - Schedule management endpoints (`src/routes/schedules.js`)
  - **Controller Layer**:
    - Request validation and response formatting
    - Error handling and status code management
    - Coordination between multiple services
  - **Service Layer**:
    - Optimization job management (`src/services/optimizationService.js`)
    - File handling (`src/services/fileService.js`)
    - User authentication (`src/services/userService.js`)
    - Schedule operations (`src/services/scheduleService.js`)
  - **Middleware Layer**:
    - JWT-based authentication (`src/middleware/auth.js`)
    - Error handling middleware
    - Logging middleware
  - **Utility Layer**:
    - Custom error classes and handlers (`src/utils/errorHandler.js`)
    - Database connection helpers
    - Request/response formatting utilities
- ✅ Developed robust communication with optimizer service:
  - HTTP-based API interaction
  - File transfer for input data
  - Job status polling and result retrieval
  - Error handling and recovery strategies
- ✅ Implemented secure authentication system:
  - Password hashing with bcrypt
  - JWT-based token authentication
  - Role-based access control
  - Secure password reset flow
- ✅ Created comprehensive file management:
  - File upload with validation
  - Secure file storage and retrieval
  - Association with database records
  - Future S3 integration support

### Database Schema Implementation
- ✅ **Authentication and Users**:
  - `users` table with secure password storage
  - Role-based permissions system
  - Account management fields
- ✅ **Core Scheduling Entities**:
  - `periods` table defining school time slots
  - `courses` table for curriculum offerings
  - `teachers` table with faculty information
  - `students` table with learner records
  - `sections` table connecting courses, teachers, and periods
- ✅ **Relationship Tables**:
  - `teacher_unavailability` for faculty constraints
  - `student_preferences` for course selection
  - `enrollments` for student-section assignments
  - `schedule_sections` and `schedule_assignments` for saved schedules
- ✅ **Operational Tables**:
  - `optimization_jobs` for tracking processing status
  - `input_files` for managing uploaded data
  - `schedules` for storing generated solutions

### Pending Work and Next Steps
- ⏳ **Frontend Development**:
  - React-based SPA with responsive design
  - Component library with consistent styling
  - State management using React Context or Redux
  - Form handling with validation
  
- ⏳ **Advanced Optimization**:
  - MILP algorithm implementation
  - Integration with Gurobi solver
  - Performance optimization for large datasets
  - Additional constraint handling
  
- ⏳ **System Integration**:
  - End-to-end testing of complete workflow
  - AWS S3 integration for scalable file storage
  - CI/CD pipeline setup
  - Production deployment configuration
  
- ⏳ **Reporting and Analytics**:
  - Schedule quality metrics
  - Constraint satisfaction reporting
  - Visual analytics dashboard
  - Export options for various formats

### Directory Structure

```
scheduling-platform/
├── docker/                      # Docker configuration files
│   ├── backend.Dockerfile       # Node.js backend container config
│   ├── frontend.Dockerfile      # React frontend container config
│   ├── optimizer.Dockerfile     # Python optimizer container config
│   └── gurobi.lic               # Gurobi license file for optimizer
│
├── backend/                     # Node.js API server
│   ├── src/                     # Source code
│   │   ├── routes/              # API route definitions
│   │   ├── controllers/         # Request handlers
│   │   ├── services/            # Business logic
│   │   ├── models/              # Data access
│   │   ├── middleware/          # Cross-cutting concerns
│   │   ├── utils/               # Utilities
│   │   └── index.js             # Main entry point
│   ├── tests/                   # Test suite
│   ├── package.json             # Dependencies
│   └── Dockerfile               # Container configuration
│
├── frontend/                    # React frontend application
│   ├── src/                     # Source code
│   │   ├── components/          # UI components
│   │   ├── pages/               # Route pages
│   │   ├── services/            # API clients
│   │   ├── hooks/               # Custom React hooks
│   │   ├── context/             # State management
│   │   ├── utils/               # Utilities
│   │   └── App.js               # Main component
│   ├── public/                  # Static assets
│   ├── package.json             # Dependencies
│   └── Dockerfile               # Container configuration
│
├── optimizer/                   # Python optimization service
│   ├── src/                     # Source code
│   │   ├── algorithms/          # Optimization algorithms
│   │   ├── data/                # Data processing
│   │   ├── models/              # Domain models
│   │   ├── utils/               # Utilities
│   │   ├── api.py               # REST API
│   │   ├── cli.py               # Command-line interface
│   │   └── optimizer.py         # Core service
│   ├── tests/                   # Test suite
│   ├── requirements.txt         # Dependencies
│   └── Dockerfile               # Container configuration
│
├── database/                    # Database configuration
│   ├── init.sql                 # Schema initialization
│   ├── migrations/              # Schema migrations
│   └── seeds/                   # Sample data
│
├── nginx/                       # Web server configuration
│   └── nginx.conf               # Nginx configuration
│
├── scripts/                     # Utility scripts
│   ├── setup/                   # Setup scripts
│   └── deployment/              # Deployment scripts
│
├── docker-compose.yml           # Multi-container definition
└── .env                         # Environment variables
```

## Setup and Installation

### Prerequisites

- AWS EC2 instance (recommended: t3.large or better with 16GB+ RAM)
- Docker and Docker Compose installed
- AWS S3 bucket for file storage
- Gurobi license key: ba446ea2-f2f6-4614-8e8f-aa378d1404b5

### Installation Steps

1. Clone this repository to your EC2 instance
2. The Gurobi license key is already configured in the Dockerfile
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

### Testing Components

To verify that the system components are working correctly, use the provided test scripts:

1. Test the integrated optimization pipeline with Docker:
   ```
   sudo ./test_optimizer_pipeline.sh
   ```
   This test:
   - Builds a Docker container with all necessary dependencies
   - Runs the complete optimization pipeline:
     - Greedy algorithm → MILP optimization → Claude agent section adjustments
     - Iterates until all sections meet the 75% utilization threshold
   - Generates output files in the pipeline_test/output directory

2. Test Gurobi functionality:
   ```
   # Inside the optimizer container
   docker-compose exec optimizer python /app/test_gurobi.py
   ```

3. View test results and HTML dashboard:
   ```
   ls -la pipeline_test/output/final/
   # To view the dashboard in a browser
   firefox pipeline_test/output/final/dashboard.html
   ```

The test environment automatically handles the Gurobi license (ba446ea2-f2f6-4614-8e8f-aa378d1404b5) setup and validation.

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

The platform includes two main scheduling algorithms plus an integrated optimization pipeline:

1. **Greedy Algorithm** (`optimizer/src/algorithms/greedy.py`):
   - Fast initial scheduling
   - Used for generating initial solutions
   - Good for quick previews and testing
   - Two-phase approach:
     - First schedule sections to periods based on constraints and priorities
     - Then assign students to sections based on preferences and availability
   - Uses heuristics to prioritize difficult-to-schedule sections and students
   - Handles constraints like teacher availability and special course period restrictions

2. **Mixed Integer Linear Programming** (`optimizer/src/algorithms/milp.py`):
   - Optimal scheduling with soft constraints
   - Uses Gurobi solver for high-quality results
   - Handles complex constraints and priorities
   - More computationally intensive but produces better schedules
   - Can use the greedy algorithm's solution as a starting point

3. **Integrated Optimization Pipeline** (`optimizer/src/pipeline.py`):
   - Comprehensive optimization workflow that combines multiple algorithms
   - Process flow:
     1. Uses greedy algorithm to generate a warm start solution
     2. Feeds the warm start into MILP for optimal scheduling using Gurobi
     3. Identifies underutilized sections (below 75% capacity)
     4. Uses Claude AI assistant to recommend section adjustments
     5. Implements adjustments and repeats until all sections have 75% or greater utilization
   - Section adjustment options:
     - SPLIT: Divide a section into two smaller sections
     - ADD: Create a new section to meet demand
     - REMOVE: Remove a section with insufficient demand
     - MERGE: Combine two sections with low enrollment
   - Generates comprehensive reports and a HTML dashboard with results
   - Automatically handles Gurobi licensing with key: ba446ea2-f2f6-4614-8e8f-aa378d1404b5

You can run the integrated pipeline using:
```
python run_optimizer.py --input "Test Input Files/" --output "results/" --threshold 0.75 --max-iterations 5
```

## Development Guide

### Adding New Features

1. **Backend Changes**:
   - Add routes in `backend/src/routes/`
   - Implement controllers in `backend/src/controllers/`
   - Add business logic in `backend/src/services/`
   - Define database queries in `backend/src/models/`
   - Each component should follow the pattern used in the existing code:
     - Routes define endpoints and connect to controllers
     - Controllers handle request/response flow and call services
     - Services contain business logic and interact with database/external services

2. **Frontend Updates**:
   - Add components in `frontend/src/components/`
   - Update pages in `frontend/src/pages/`
   - Extend API client in `frontend/src/services/`
   - Follow React best practices with functional components and hooks
   - Maintain consistent styling using the UI framework

3. **Optimizer Improvements**:
   - Modify algorithms in `optimizer/src/algorithms/`
   - Update API endpoints in `optimizer/src/api.py`
   - Enhance data processing in `optimizer/src/data/`
   - Extend domain models in `optimizer/src/models/`
   - Add new constraints or objective functions
   - Follow test-driven development by adding tests for new functionality

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
  
- **Gurobi License Issues**:
  - If you see "License expired" or "not recognized as belonging to an academic domain" errors
  - The system will automatically fall back to using the greedy algorithm
  - For best results, run the system from an academic network or through a university VPN
  - The license key (ba446ea2-f2f6-4614-8e8f-aa378d1404b5) is already configured in the system

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