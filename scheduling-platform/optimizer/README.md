# School Schedule Optimizer

This component provides the core scheduling optimization service for the school scheduling platform. It takes input data files describing students, teachers, courses, and constraints, and generates optimal schedules.

## Features

- Multiple optimization algorithms (greedy, MILP)
- REST API for integration with other services
- Command-line interface for batch processing
- Comprehensive data validation
- Detailed output reports

## Installation

### Requirements

- Python 3.9+
- pandas
- numpy
- Flask (for API mode)
- Gurobi (optional, for MILP optimization)

### Setup

```bash
# Install the package
pip install -e ".[dev]"

# For Gurobi support (optional)
pip install -e ".[gurobi]"
```

## Usage

### Command-line Interface

```bash
# Basic usage with default options (greedy algorithm)
schedule-optimizer --input-dir /path/to/input --output-dir /path/to/output

# Use MILP algorithm
schedule-optimizer --input-dir /path/to/input --output-dir /path/to/output --algorithm milp

# Help
schedule-optimizer --help
```

### API Server

```bash
# Start the API server
schedule-optimizer --mode api --port 5000

# API endpoints:
# - GET /api/v1/health - Health check
# - GET /api/v1/jobs - List jobs
# - GET /api/v1/jobs/{job_id} - Get job details
# - POST /api/v1/optimize - Submit new optimization job
# - GET /api/v1/jobs/{job_id}/download/{file_type} - Download results
# - DELETE /api/v1/jobs/{job_id} - Delete job
```

## Input Data

The optimizer expects the following CSV files in the input directory:

1. `Student_Info.csv` - Student information
2. `Teacher_Info.csv` - Teacher information
3. `Sections_Information.csv` - Section information
4. `Period.csv` - Period definitions
5. `Student_Preference_Info.csv` - Student course preferences
6. `Teacher_unavailability.csv` - Teacher unavailability periods (optional)

## Output Files

The optimizer generates the following CSV files:

1. `Master_Schedule.csv` - Complete schedule with sections assigned to periods
2. `Student_Assignments.csv` - Student assignments to sections
3. `Teacher_Schedule.csv` - Teacher schedule
4. `Utilization_Report.csv` - Section utilization report

## Development

### Running Tests

```bash
# Run all tests
pytest

# Run with coverage report
pytest --cov=src

# Run specific test
pytest tests/test_optimizer.py::TestScheduleOptimizer::test_optimization
```

### Project Structure

```
optimizer/
├── src/                  # Source code
│   ├── algorithms/       # Optimization algorithms
│   ├── data/             # Data handling
│   ├── models/           # Domain models
│   ├── utils/            # Utilities
│   ├── cli.py            # Command-line interface
│   ├── api.py            # REST API
│   └── optimizer.py      # Main optimizer service
├── tests/                # Tests
├── main.py               # Entry point
├── setup.py              # Package configuration
└── README.md             # This file
```

## License

Proprietary. All rights reserved.