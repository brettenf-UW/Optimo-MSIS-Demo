#!/bin/bash

# Test script using Docker containers to validate components

echo "==== School Scheduling Platform Testing ===="
echo ""
echo "This script will test the major components of the scheduling platform"
echo "using Docker containers to isolate the environment."
echo ""

# STEP 1: Check if Docker is available
if ! command -v docker &> /dev/null; then
    echo "❌ Docker not found. Please install Docker first."
    exit 1
fi

# STEP 2: Test Optimizer Component
echo "Testing Optimizer Component..."
echo "=============================="

echo "Building Optimizer container..."
docker build -t scheduling-optimizer-test -f scheduling-platform/optimizer/Dockerfile scheduling-platform/optimizer/

if [ $? -ne 0 ]; then
    echo "❌ Failed to build optimizer image."
    exit 1
fi

echo "Running Gurobi license check..."
docker run --rm scheduling-optimizer-test python -c "import gurobipy; print('Gurobi license is working!')"

echo "Running Optimizer test with test data..."
docker run --rm \
    -v "$(pwd)/Test Input Files:/app/input" \
    -v "$(pwd)/test_results:/app/output" \
    scheduling-optimizer-test python -m tests.test_with_data

if [ $? -ne 0 ]; then
    echo "❌ Optimizer tests failed."
    exit 1
else
    echo "✅ Optimizer tests passed."
fi

# STEP 3: Test Backend Component
echo ""
echo "Testing Backend Component..."
echo "==========================="

echo "Building Backend container..."
docker build -t scheduling-backend-test -f scheduling-platform/backend/Dockerfile scheduling-platform/backend/

if [ $? -ne 0 ]; then
    echo "❌ Failed to build backend image."
    exit 1
fi

echo "Running Backend tests..."
docker run --rm scheduling-backend-test npm test

if [ $? -ne 0 ]; then
    echo "❌ Backend tests failed."
    exit 1
else
    echo "✅ Backend tests passed."
fi

# STEP 4: Results
echo ""
echo "==== Testing Completed ===="
echo "✅ All components tested successfully!"
echo ""
echo "Check test_results directory for optimizer output files."
echo ""