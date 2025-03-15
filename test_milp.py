#!/usr/bin/env python3
"""
Test script for MILP optimizer to isolate and debug issues.
"""
import os
import sys
import logging
from pathlib import Path

# Configure logging
logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Add the scheduling-platform directory to the Python path
sys.path.append(str(Path(__file__).parent / "scheduling-platform/optimizer"))

# Import the necessary modules
from src.data.loader import ScheduleDataLoader
from src.data.converter import DataConverter
from src.algorithms.milp import MILPOptimizer
from src.algorithms.greedy import GreedyOptimizer
from src.models.entities import Schedule, Section, Period

def test_milp_only():
    """Test just the MILP optimizer with clean data."""
    logger.info("Starting MILP-only test")
    
    # Load data
    input_dir = Path("Test Input Files")
    data_loader = ScheduleDataLoader(str(input_dir))
    data = data_loader.load_all()
    
    # Convert data
    converter = DataConverter()
    domain_data = {
        'students': converter.convert_students(data['students']),
        'teachers': converter.convert_teachers(
            data['teachers'], 
            data.get('teacher_unavailability')
        ),
        'sections': converter.convert_sections(data['sections']),
        'periods': converter.convert_periods(data['periods']),
        'student_preferences': converter.convert_preferences(data['student_preferences'])
    }
    
    students = domain_data['students']
    teachers = domain_data['teachers']
    sections = domain_data['sections']
    periods = domain_data['periods']
    student_preferences = domain_data['student_preferences']
    
    # Log key data counts
    logger.info(f"Loaded {len(students)} students, {len(teachers)} teachers, {len(sections)} sections, {len(periods)} periods")
    
    # Create a fresh MILP optimizer without warm start
    logger.info("Creating MILP optimizer without warm start")
    milp_optimizer_no_warmstart = MILPOptimizer(
        students=students,
        teachers=teachers,
        sections=sections,
        periods=periods,
        student_preferences=student_preferences,
        warm_start=None,
        time_limit_seconds=300  # 5 minutes max
    )
    
    # Run MILP optimization without warm start
    logger.info("Running MILP optimization without warm start")
    try:
        schedule_no_warmstart = milp_optimizer_no_warmstart.optimize()
        scheduled_sections = len([s for s in schedule_no_warmstart.sections.values() if s.is_scheduled])
        logger.info(f"MILP without warm start: scheduled {scheduled_sections}/{len(sections)} sections")
        
        # Log special sections placement
        special_sections = {}
        for section_id, section in schedule_no_warmstart.sections.items():
            if section.is_scheduled and section.course_id in ['Medical Career', 'Heroes Teach']:
                if section.course_id not in special_sections:
                    special_sections[section.course_id] = []
                special_sections[section.course_id].append((section_id, section.period_id))
                
        for course, placements in special_sections.items():
            logger.info(f"{course} sections placed in: {placements}")
            
    except Exception as e:
        logger.error(f"MILP without warm start failed: {str(e)}")
    
    # Now run with greedy + warm start
    logger.info("\nRunning greedy algorithm for warm start")
    greedy_optimizer = GreedyOptimizer(
        students=students,
        teachers=teachers,
        sections=sections,
        periods=periods,
        student_preferences=student_preferences
    )
    
    greedy_schedule = greedy_optimizer.optimize()
    
    # Log the greedy schedule's special sections
    special_sections_greedy = {}
    for section_id, section in greedy_schedule.sections.items():
        if section.is_scheduled and section.course_id in ['Medical Career', 'Heroes Teach']:
            if section.course_id not in special_sections_greedy:
                special_sections_greedy[section.course_id] = []
            special_sections_greedy[section.course_id].append((section_id, section.period_id))
            
    for course, placements in special_sections_greedy.items():
        logger.info(f"Greedy placed {course} sections in: {placements}")
    
    # Create MILP optimizer with greedy warm start
    logger.info("\nCreating MILP optimizer with greedy warm start but NO constraints")
    
    # Create a modified MILP optimizer without period restrictions for warm start test
    class TestMILPOptimizerNoConstraints(MILPOptimizer):
        def __init__(self, *args, **kwargs):
            super().__init__(*args, **kwargs)
            # Override the course period restrictions to empty
            self.course_period_restrictions = {}
    
    milp_optimizer_warmstart_no_constraints = TestMILPOptimizerNoConstraints(
        students=students,
        teachers=teachers,
        sections=sections,
        periods=periods,
        student_preferences=student_preferences,
        warm_start=greedy_schedule,
        time_limit_seconds=300  # 5 minutes max
    )
    
    # Run MILP optimization with warm start but no constraints
    logger.info("Running MILP optimization with warm start but NO constraints")
    try:
        schedule_warmstart_no_constraints = milp_optimizer_warmstart_no_constraints.optimize()
        scheduled_sections = len([s for s in schedule_warmstart_no_constraints.sections.values() if s.is_scheduled])
        logger.info(f"MILP with warm start but NO constraints: scheduled {scheduled_sections}/{len(sections)} sections")
    except Exception as e:
        logger.error(f"MILP with warm start but NO constraints failed: {str(e)}")
    
    # Try with normal MILP + warm start
    logger.info("\nCreating MILP optimizer with warm start and constraints")
    milp_optimizer_warmstart = MILPOptimizer(
        students=students,
        teachers=teachers,
        sections=sections,
        periods=periods,
        student_preferences=student_preferences,
        warm_start=greedy_schedule,
        time_limit_seconds=300  # 5 minutes max
    )
    
    # Run MILP optimization with warm start
    logger.info("Running MILP optimization with warm start and constraints")
    try:
        schedule_warmstart = milp_optimizer_warmstart.optimize()
        scheduled_sections = len([s for s in schedule_warmstart.sections.values() if s.is_scheduled])
        logger.info(f"MILP with warm start and constraints: scheduled {scheduled_sections}/{len(sections)} sections")
    except Exception as e:
        logger.error(f"MILP with warm start and constraints failed: {str(e)}")
    
    # Create a fixed warm start schedule where special sections are manually placed in allowed periods
    logger.info("\nCreating a manually fixed warm start schedule")
    fixed_schedule = Schedule()
    
    # Copy sections from greedy schedule
    for section_id, section in greedy_schedule.sections.items():
        section_copy = Section(
            id=section.id,
            course_id=section.course_id,
            teacher_id=section.teacher_id,
            capacity=section.capacity
        )
        
        # Set period based on restrictions for special courses
        if section.course_id == 'Medical Career':
            # Place in R1 or G1
            section_copy.period_id = 'R1'
        elif section.course_id == 'Heroes Teach':
            # Place in R2 or G2
            section_copy.period_id = 'R2'
        elif section.is_scheduled:
            # Keep original period for non-special courses
            section_copy.period_id = section.period_id
            
        fixed_schedule.sections[section_id] = section_copy
    
    # Copy assignments from greedy schedule
    fixed_schedule.assignments = greedy_schedule.assignments
    
    # Create MILP optimizer with fixed warm start
    logger.info("\nCreating MILP optimizer with fixed warm start")
    milp_optimizer_fixed = MILPOptimizer(
        students=students,
        teachers=teachers,
        sections=sections,
        periods=periods,
        student_preferences=student_preferences,
        warm_start=fixed_schedule,
        time_limit_seconds=300  # 5 minutes max
    )
    
    # Run MILP optimization with fixed warm start
    logger.info("Running MILP optimization with fixed warm start")
    try:
        schedule_fixed = milp_optimizer_fixed.optimize()
        scheduled_sections = len([s for s in schedule_fixed.sections.values() if s.is_scheduled])
        logger.info(f"MILP with fixed warm start: scheduled {scheduled_sections}/{len(sections)} sections")
    except Exception as e:
        logger.error(f"MILP with fixed warm start failed: {str(e)}")
    
    logger.info("MILP testing complete")

if __name__ == "__main__":
    test_milp_only()