"""
Test script to run the optimizer with actual input data files.
To be executed within the Docker container.

This test uses the Gurobi license key: ba446ea2-f2f6-4614-8e8f-aa378d1404b5
"""
import sys
import os
from pathlib import Path

# Add parent directory to Python path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

# Import optimizer components
from src.optimizer import ScheduleOptimizer

def main():
    """Run a test optimization using actual data files within the Docker container."""
    print("Starting optimizer test in Docker container...")
    
    # Define paths - in Docker container /app/input contains the mounted test files
    input_dir = Path("/app/input")
    output_dir = Path("/app/output")
    
    print(f"Input directory: {input_dir}")
    print(f"Output directory: {output_dir}")
    
    # Check if input files exist
    required_files = [
        "Period.csv",
        "Sections_Information.csv",
        "Student_Info.csv",
        "Student_Preference_Info.csv",
        "Teacher_Info.csv",
        "Teacher_unavailability.csv"
    ]
    
    missing_files = []
    for file in required_files:
        if not (input_dir / file).exists():
            missing_files.append(file)
    
    if missing_files:
        print(f"Error: Missing input files: {', '.join(missing_files)}")
        return False
    
    # Create output directory if it doesn't exist
    output_dir.mkdir(exist_ok=True)
    
    try:
        # Initialize the optimizer
        print("Initializing optimizer...")
        optimizer = ScheduleOptimizer(input_dir, output_dir)
        
        # Run optimization process
        print("Running optimization...")
        results = optimizer.optimize()
        
        # Check success
        if results['success']:
            print("\n✅ Optimization completed successfully!")
            print(f"\nSchedule Summary:")
            for key, value in results['schedule_summary'].items():
                print(f"  - {key}: {value}")
            
            print(f"\nOutput Files:")
            for key, file in results['output_files'].items():
                print(f"  - {key}: {file}")
            
            print(f"\nMetrics:")
            for key, value in results['metrics'].items():
                print(f"  - {key}: {value:.2f} seconds")
            
            return True
        else:
            print(f"\n❌ Optimization failed: {results.get('error', 'Unknown error')}")
            return False
            
    except Exception as e:
        print(f"\n❌ Error during test: {str(e)}")
        import traceback
        traceback.print_exc()
        return False


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)