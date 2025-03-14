#!/usr/bin/env python3
"""
Main entry point for the school scheduling optimizer.
Provides options to run the optimizer in different modes:
- CLI mode: Run the optimizer from the command line
- API mode: Start a REST API server
"""
import sys
import os
import argparse
from src.cli import main as cli_main
from src.api import app as api_app


def parse_args():
    """Parse command-line arguments for the main entry point."""
    parser = argparse.ArgumentParser(
        description='School Schedule Optimizer',
        formatter_class=argparse.ArgumentDefaultsHelpFormatter
    )
    
    parser.add_argument(
        '--mode',
        type=str,
        choices=['cli', 'api'],
        default='cli',
        help='Mode to run the optimizer in'
    )
    
    parser.add_argument(
        '--port',
        type=int,
        default=5000,
        help='Port to run the API server on (only in API mode)'
    )
    
    parser.add_argument(
        '--host',
        type=str,
        default='0.0.0.0',
        help='Host to bind the API server to (only in API mode)'
    )
    
    # Parse known args and pass the rest to the appropriate mode
    return parser.parse_known_args()


def main():
    """Main entry point."""
    # Parse arguments
    args, remaining = parse_args()
    
    # Run in the selected mode
    if args.mode == 'cli':
        # Add remaining args to sys.argv for cli_main to parse
        sys.argv = [sys.argv[0]] + remaining
        cli_main()
    
    elif args.mode == 'api':
        # Start API server
        print(f"Starting API server on {args.host}:{args.port}")
        api_app.run(host=args.host, port=args.port)
    
    else:
        print(f"Invalid mode: {args.mode}")
        sys.exit(1)


if __name__ == '__main__':
    main()