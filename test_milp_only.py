#!/usr/bin/env python3
"""
Focused test script for MILP optimizer with extensive debugging info.
"""
import os
import sys
import time
import logging
import pandas as pd
from pathlib import Path

# Configure very detailed logging
logging.basicConfig(
    level=logging.DEBUG, 
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler("milp_test.log")
    ]
)
logger = logging.getLogger("milp_test")

# Add the scheduling-platform directory to the Python path
sys.path.append(str(Path(__file__).parent / "scheduling-platform/optimizer"))

# Import needed modules
from src.data.loader import ScheduleDataLoader
from src.algorithms.milp import MILPOptimizer
from src.models.entities import Schedule, Section

def test_clean_milp():
    """Test MILP optimizer from scratch with no warm start."""
    logger.info("=" * 80)
    logger.info("TESTING MILP OPTIMIZER (NO WARM START)")
    logger.info("=" * 80)
    
    # Load data using data loader
    input_dir = Path("Test Input Files")
    data_loader = ScheduleDataLoader(str(input_dir))
    data = data_loader.load_all()
    
    # Need to convert raw data to domain objects
    sections_df = data['sections']
    students_df = data['students']
    teachers_df = data['teachers']
    periods_df = data['periods']
    student_prefs_df = data['student_preferences']
    teacher_unavail_df = data.get('teacher_unavailability', pd.DataFrame())
    
    # Now manually set up the domain objects
    from src.data.converter import DataConverter
    converter = DataConverter()
    
    # Convert data to domain objects
    domain_students = converter.convert_students(students_df)
    domain_teachers = converter.convert_teachers(teachers_df, teacher_unavail_df)
    domain_sections = converter.convert_sections(sections_df)
    domain_periods = converter.convert_periods(periods_df)
    domain_preferences = converter.convert_preferences(student_prefs_df)
    
    # Create a MILP optimizer without warm start
    logger.info(f"Creating MILP optimizer with {len(domain_students)} students, " 
                f"{len(domain_teachers)} teachers, {len(domain_sections)} sections, "
                f"{len(domain_periods)} periods")
    
    # Print special courses for verification
    special_sections = []
    for section_id, section in domain_sections.items():
        if section.course_id in ['Medical Career', 'Heroes Teach']:
            special_sections.append((section_id, section.course_id))
    
    logger.info(f"Special sections: {special_sections}")
    
    # Create optimizer with a shorter timeout for testing
    milp_optimizer = MILPOptimizer(
        students=domain_students,
        teachers=domain_teachers,
        sections=domain_sections,
        periods=domain_periods,
        student_preferences=domain_preferences,
        warm_start=None,  # No warm start
        time_limit_seconds=300  # 5 minutes max
    )
    
    # Verify period restrictions
    logger.info("Course period restrictions:")
    for course, periods in milp_optimizer.course_period_restrictions.items():
        logger.info(f"  {course}: {periods}")
    
    # Run optimization with proper error handling
    try:
        logger.info("Starting MILP optimization...")
        start_time = time.time()
        schedule = milp_optimizer.optimize()
        elapsed_time = time.time() - start_time
        
        logger.info(f"Optimization completed in {elapsed_time:.2f} seconds")
        scheduled_sections = len([s for s in schedule.sections.values() if s.is_scheduled])
        logger.info(f"Scheduled {scheduled_sections}/{len(domain_sections)} sections")
        
        # Log special section placements
        logger.info("Special section placements:")
        for section_id, section in schedule.sections.items():
            if section.is_scheduled and section.course_id in ['Medical Career', 'Heroes Teach']:
                logger.info(f"  {section_id} ({section.course_id}): {section.period_id}")
        
        # Verify constraints
        logger.info("Verifying period constraints for special courses...")
        all_valid = True
        for section_id, section in schedule.sections.items():
            if not section.is_scheduled:
                continue
                
            if section.course_id == 'Medical Career':
                if section.period_id not in ['R1', 'G1']:
                    logger.error(f"CONSTRAINT VIOLATION: {section_id} ({section.course_id}) in period {section.period_id}")
                    all_valid = False
            elif section.course_id == 'Heroes Teach':
                if section.period_id not in ['R2', 'G2']:
                    logger.error(f"CONSTRAINT VIOLATION: {section_id} ({section.course_id}) in period {section.period_id}")
                    all_valid = False
        
        if all_valid:
            logger.info("All special course constraints satisfied!")
        else:
            logger.error("Constraint violations detected!")
            
        return schedule
        
    except Exception as e:
        logger.exception(f"MILP optimization failed: {str(e)}")
        return None

if __name__ == "__main__":
    try:
        result = test_clean_milp()
        logger.info("Test completed!")
    except Exception as e:
        logger.exception(f"Test failed with exception: {str(e)}")