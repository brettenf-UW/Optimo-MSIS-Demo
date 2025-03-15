#!/usr/bin/env python3
"""
School Schedule Optimization Pipeline Runner

This script provides a simple entry point to run the full optimization pipeline,
which includes:
1. Greedy algorithm for warm start
2. MILP optimization with the warm start
3. Section adjustment via Claude agent for underutilized sections
4. Iteration until all sections meet utilization targets

Usage:
  python run_optimizer.py --input Test\ Input\ Files/ --output results/
"""
import os
import sys
import argparse
import logging
from pathlib import Path

# Add the scheduling platform to the Python path
script_dir = Path(__file__).parent.absolute()
optimizer_path = script_dir / "scheduling-platform" / "optimizer"
sys.path.append(str(optimizer_path))

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler("optimizer.log")
    ]
)
logger = logging.getLogger(__name__)

def main():
    """
    Main entry point for the script.
    Parses command line arguments and runs the optimization pipeline.
    """
    parser = argparse.ArgumentParser(description="School Schedule Optimization Pipeline")
    parser.add_argument("--input", type=str, required=True, help="Directory with input files")
    parser.add_argument("--output", type=str, required=True, help="Directory for output files")
    parser.add_argument("--threshold", type=float, default=0.75, help="Minimum utilization threshold (0-1)")
    parser.add_argument("--max-iterations", type=int, default=5, help="Maximum number of iterations")
    parser.add_argument("--algorithm", type=str, default="both", choices=["greedy", "milp", "both"], 
                       help="Which algorithm to use: greedy, milp, or both")
    parser.add_argument("--claude-api-key", type=str, 
                       default="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",
                       help="Claude API key for section adjustment")
    args = parser.parse_args()

    # Verify paths
    input_dir = Path(args.input)
    if not input_dir.exists():
        logger.error(f"Input directory does not exist: {input_dir}")
        return 1

    output_dir = Path(args.output)
    output_dir.mkdir(parents=True, exist_ok=True)

    # Import here to avoid module issues
    from src.pipeline import OptimizationPipeline

    # Initialize the pipeline
    pipeline = OptimizationPipeline(
        input_dir=input_dir,
        output_dir=output_dir,
        utilization_threshold=args.threshold
    )

    # Set max iterations
    pipeline.max_iterations = args.max_iterations

    # Run the pipeline
    try:
        logger.info(f"Starting optimization with input: {input_dir}, output: {output_dir}")
        results = pipeline.run()
        
        # Print summary
        logger.info("\nOptimization Pipeline Complete!")
        logger.info(f"Final results saved to: {results['output_dir']}")
        logger.info(f"Total iterations: {results['iterations']}")
        logger.info(f"Total time: {results['metrics']['total_time']:.2f} seconds")
        
        # Print location of HTML dashboard
        dashboard_path = Path(results['output_dir']) / "dashboard.html"
        if dashboard_path.exists():
            logger.info(f"View results dashboard at: {dashboard_path}")
            
        return 0
    except Exception as e:
        logger.error(f"Error during optimization: {str(e)}", exc_info=True)
        return 1

if __name__ == "__main__":
    sys.exit(main())