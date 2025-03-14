#!/usr/bin/env python3
"""
Command-line interface for the school scheduling optimizer.
Provides a simple way to run the optimizer from the command line.
"""
import argparse
import logging
import json
import sys
from pathlib import Path
from .optimizer import ScheduleOptimizer


def parse_args():
    """Parse command-line arguments."""
    parser = argparse.ArgumentParser(
        description='School Schedule Optimizer CLI',
        formatter_class=argparse.ArgumentDefaultsHelpFormatter
    )
    
    parser.add_argument(
        '--input-dir',
        type=str,
        default='input',
        help='Directory containing input CSV files'
    )
    
    parser.add_argument(
        '--output-dir',
        type=str,
        default='output',
        help='Directory to save output CSV files'
    )
    
    parser.add_argument(
        '--algorithm',
        type=str,
        choices=['greedy', 'milp'],
        default='greedy',
        help='Optimization algorithm to use'
    )
    
    parser.add_argument(
        '--log-level',
        type=str,
        choices=['DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL'],
        default='INFO',
        help='Logging level'
    )
    
    parser.add_argument(
        '--json-output',
        action='store_true',
        help='Output results as JSON'
    )
    
    return parser.parse_args()


def setup_logging(log_level):
    """Configure logging."""
    numeric_level = getattr(logging, log_level.upper(), None)
    if not isinstance(numeric_level, int):
        raise ValueError(f'Invalid log level: {log_level}')
    
    logging.basicConfig(
        level=numeric_level,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )


def main():
    """Main entry point for the CLI."""
    # Parse command-line arguments
    args = parse_args()
    
    # Setup logging
    setup_logging(args.log_level)
    
    # Ensure input directory exists
    input_dir = Path(args.input_dir)
    if not input_dir.exists():
        print(f"Error: Input directory does not exist: {input_dir}")
        sys.exit(1)
    
    # Create output directory if needed
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    
    try:
        # Create optimizer
        optimizer = ScheduleOptimizer(
            input_dir=str(input_dir),
            output_dir=str(output_dir)
        )
        
        # Run optimization
        results = optimizer.optimize(algorithm=args.algorithm)
        
        # Display results
        if args.json_output:
            # Output results as JSON
            print(json.dumps(results, indent=2))
        else:
            # Output results in human-readable format
            print("\nOptimization Results:")
            
            if results['success']:
                summary = results['schedule_summary']
                print(f"  Sections scheduled: {summary['scheduled_sections']}/{summary['total_sections']}")
                print(f"  Students assigned: {summary['total_students']}")
                print(f"  Total assignments: {summary['total_assignments']}")
                
                print("\nOutput files:")
                for name, path in results['output_files'].items():
                    print(f"  {name}: {path}")
                
                print("\nPerformance metrics:")
                for metric, value in results['metrics'].items():
                    print(f"  {metric}: {value:.2f} seconds")
            else:
                print(f"  Error: {results['error']}")
                print("\nPerformance metrics:")
                for metric, value in results['metrics'].items():
                    print(f"  {metric}: {value:.2f} seconds")
                sys.exit(1)
    
    except Exception as e:
        print(f"Error: {str(e)}")
        sys.exit(1)


if __name__ == '__main__':
    main()