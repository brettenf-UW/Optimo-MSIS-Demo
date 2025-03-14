"""
Main optimizer service module.

This module provides the core scheduling optimization service.
It orchestrates the loading of data, running optimization algorithms,
and returning the results.
"""
import pandas as pd
import logging
import time
import os
from pathlib import Path
from typing import Dict, List, Optional, Any

from .data.loader import ScheduleDataLoader
from .data.converter import DataConverter
from .models.entities import Schedule
from .algorithms.greedy import GreedyOptimizer

# Configure logging
logging.basicConfig(level=logging.INFO, 
                   format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


class ScheduleOptimizer:
    """
    Main scheduling optimization service.
    
    This class is responsible for:
    - Loading input data
    - Running optimization algorithms
    - Generating and saving results
    """
    
    def __init__(self, input_dir: str, output_dir: str):
        """
        Initialize the optimizer service.
        
        Args:
            input_dir: Directory containing input CSV files
            output_dir: Directory where output CSV files will be saved
        """
        self.input_dir = Path(input_dir)
        self.output_dir = Path(output_dir)
        
        # Create output directory if it doesn't exist
        if not self.output_dir.exists():
            self.output_dir.mkdir(parents=True, exist_ok=True)
        
        # Initialize data loader
        self.loader = ScheduleDataLoader(str(input_dir))
        self.converter = DataConverter()
        
        # Initialize optimization metrics
        self.metrics = {
            'load_time': 0,
            'conversion_time': 0,
            'optimization_time': 0,
            'total_time': 0
        }
    
    def load_data(self) -> Dict[str, pd.DataFrame]:
        """
        Load input data files.
        
        Returns:
            Dictionary of DataFrames containing the loaded data
        """
        start_time = time.time()
        logger.info(f"Loading data from {self.input_dir}")
        
        try:
            # Load using the data loader
            data = self.loader.load_all()
            
            self.metrics['load_time'] = time.time() - start_time
            logger.info(f"Data loaded successfully in {self.metrics['load_time']:.2f} seconds")
            
            return data
        except Exception as e:
            logger.error(f"Error loading data: {str(e)}")
            raise
    
    def convert_data(self, data: Dict[str, pd.DataFrame]) -> Dict[str, Any]:
        """
        Convert CSV data to domain model objects.
        
        Args:
            data: Dictionary of DataFrames
            
        Returns:
            Dictionary containing domain objects
        """
        start_time = time.time()
        logger.info("Converting data to domain model")
        
        try:
            # Convert DataFrames to domain objects
            domain_data = {
                'students': self.converter.convert_students(data['students']),
                'teachers': self.converter.convert_teachers(
                    data['teachers'], 
                    data.get('teacher_unavailability')
                ),
                'sections': self.converter.convert_sections(data['sections']),
                'periods': self.converter.convert_periods(data['periods']),
                'student_preferences': self.converter.convert_preferences(data['student_preferences'])
            }
            
            self.metrics['conversion_time'] = time.time() - start_time
            logger.info(f"Data converted successfully in {self.metrics['conversion_time']:.2f} seconds")
            
            return domain_data
        except Exception as e:
            logger.error(f"Error converting data: {str(e)}")
            raise
    
    def run_optimization(self, domain_data: Dict[str, Any], algorithm: str = 'greedy') -> Schedule:
        """
        Run the optimization algorithm.
        
        Args:
            domain_data: Dictionary containing domain objects
            algorithm: Name of the algorithm to use
            
        Returns:
            Optimized Schedule object
        """
        start_time = time.time()
        logger.info(f"Starting optimization using {algorithm} algorithm")
        
        if algorithm.lower() == 'greedy':
            # Create and run greedy optimizer
            optimizer = GreedyOptimizer(
                students=domain_data['students'],
                teachers=domain_data['teachers'],
                sections=domain_data['sections'],
                periods=domain_data['periods'],
                student_preferences=domain_data['student_preferences']
            )
            
            schedule = optimizer.optimize()
            
        elif algorithm.lower() == 'milp':
            # Import here to avoid circular imports
            from .algorithms.milp import MILPOptimizer
            
            # Create and run MILP optimizer
            optimizer = MILPOptimizer(
                students=domain_data['students'],
                teachers=domain_data['teachers'],
                sections=domain_data['sections'],
                periods=domain_data['periods'],
                student_preferences=domain_data['student_preferences'],
                time_limit_seconds=1200  # 20 minutes
            )
            
            schedule = optimizer.optimize()
            
        else:
            logger.error(f"Unknown algorithm: {algorithm}")
            raise ValueError(f"Unknown algorithm: {algorithm}")
        
        self.metrics['optimization_time'] = time.time() - start_time
        logger.info(f"Optimization completed in {self.metrics['optimization_time']:.2f} seconds")
        
        return schedule
    
    def save_results(self, schedule: Schedule) -> Dict[str, str]:
        """
        Save optimization results to CSV files.
        
        Args:
            schedule: Optimized Schedule object
            
        Returns:
            Dictionary of output file paths
        """
        logger.info(f"Saving results to {self.output_dir}")
        
        # Convert schedule to DataFrames
        master_schedule_df = self.converter.convert_to_master_schedule_df(schedule)
        student_assignments_df = self.converter.convert_to_student_assignments_df(schedule)
        teacher_schedule_df = self.converter.convert_to_teacher_schedule_df(schedule)
        utilization_report_df = self.converter.generate_utilization_report(schedule)
        
        # Define output file paths
        output_files = {
            'master_schedule': str(self.output_dir / 'Master_Schedule.csv'),
            'student_assignments': str(self.output_dir / 'Student_Assignments.csv'),
            'teacher_schedule': str(self.output_dir / 'Teacher_Schedule.csv'),
            'utilization_report': str(self.output_dir / 'Utilization_Report.csv')
        }
        
        # Save DataFrames to CSV files
        master_schedule_df.to_csv(output_files['master_schedule'], index=False)
        student_assignments_df.to_csv(output_files['student_assignments'], index=False)
        teacher_schedule_df.to_csv(output_files['teacher_schedule'], index=False)
        utilization_report_df.to_csv(output_files['utilization_report'], index=False)
        
        logger.info(f"Results saved successfully")
        
        return output_files
    
    def optimize(self, algorithm: str = 'greedy') -> Dict[str, Any]:
        """
        Run the complete optimization process.
        
        Args:
            algorithm: Name of the algorithm to use
            
        Returns:
            Dictionary containing optimization results and metrics
        """
        total_start_time = time.time()
        logger.info(f"Starting complete optimization process")
        
        try:
            # Load data
            data = self.load_data()
            
            # Convert data
            domain_data = self.convert_data(data)
            
            # Run optimization
            schedule = self.run_optimization(domain_data, algorithm)
            
            # Save results
            output_files = self.save_results(schedule)
            
            # Calculate total time
            self.metrics['total_time'] = time.time() - total_start_time
            
            # Create results summary
            results = {
                'schedule_summary': {
                    'total_sections': len(schedule.sections),
                    'scheduled_sections': len([s for s in schedule.sections.values() if s.is_scheduled]),
                    'total_assignments': len(schedule.assignments),
                    'total_students': len(set(a.student_id for a in schedule.assignments))
                },
                'output_files': output_files,
                'metrics': self.metrics,
                'success': True
            }
            
            logger.info(f"Optimization completed successfully in {self.metrics['total_time']:.2f} seconds")
            
            return results
            
        except Exception as e:
            logger.error(f"Optimization failed: {str(e)}")
            
            # Calculate total time
            self.metrics['total_time'] = time.time() - total_start_time
            
            # Create error results
            results = {
                'error': str(e),
                'metrics': self.metrics,
                'success': False
            }
            
            return results