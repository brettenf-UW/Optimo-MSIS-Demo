#!/bin/bash

# Test script for running the integrated optimization pipeline inside Docker

echo "==== School Schedule Optimization Pipeline Test ===="
echo ""
echo "This script will test the integrated optimization pipeline using Docker containers"
echo ""

# Create output directories
mkdir -p pipeline_test/output

# Build the optimizer Docker image
echo "Building optimizer Docker image..."
docker build -t school-optimizer:latest -f scheduling-platform/optimizer/Dockerfile scheduling-platform/optimizer/

# Run the optimizer pipeline in Docker
echo "Running optimization pipeline..."
docker run --rm \
    -v "$(pwd)/Test Input Files:/app/input" \
    -v "$(pwd)/pipeline_test/output:/app/output" \
    school-optimizer:latest python -c "
import os
import sys
import logging
from pathlib import Path
from src.pipeline import OptimizationPipeline

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger()

# Set up paths
input_dir = Path('/app/input')
output_dir = Path('/app/output')

# Run the pipeline
try:
    print('Starting optimization pipeline...')
    pipeline = OptimizationPipeline(
        input_dir=input_dir,
        output_dir=output_dir,
        utilization_threshold=0.75  # 75% as specified
    )
    
    # Set max iterations to 5 to allow for multiple optimization passes
    pipeline.max_iterations = 5
    
    # Run the pipeline
    results = pipeline.run()
    
    # Print summary
    print('\nOptimization Pipeline Complete!')
    print(f'Final results saved to: {results[\"output_dir\"]}')
    print(f'Total iterations: {results[\"iterations\"]}')
    print(f'Total time: {results[\"metrics\"][\"total_time\"]:.2f} seconds')
    
except Exception as e:
    print(f'Error during optimization: {str(e)}')
    import traceback
    traceback.print_exc()
    sys.exit(1)
"

# Check if pipeline completed successfully
if [ $? -eq 0 ]; then
    echo "✅ Optimization pipeline test completed successfully!"
    echo "Results are available in the pipeline_test/output directory"
    
    # List the output files
    echo ""
    echo "Generated output files:"
    ls -la pipeline_test/output/final/
else
    echo "❌ Optimization pipeline test failed!"
    exit 1
fi