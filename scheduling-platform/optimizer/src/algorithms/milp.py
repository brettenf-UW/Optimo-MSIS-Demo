"""
Mixed Integer Linear Programming Optimizer for School Scheduling.

This module provides an implementation of the MILP approach to school scheduling
using the Gurobi solver. It creates a comprehensive mathematical model that
accounts for all hard constraints and optimizes for soft preferences.

License key: ba446ea2-f2f6-4614-8e8f-aa378d1404b5
"""
import logging
import time
from typing import Dict, List, Set, Any, Tuple, Optional

import gurobipy as gp
from gurobipy import GRB

from ..models.entities import Student, Teacher, Section, Period, Schedule
from ..models.entities import StudentPreference, Assignment

# Configure logging
logging.basicConfig(level=logging.INFO, 
                   format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


class MILPOptimizer:
    """
    Mixed Integer Linear Programming Optimizer for school scheduling.
    Uses Gurobi to find an optimal solution for section scheduling and
    student assignments while respecting all constraints.
    """
    
    def __init__(self, 
                 students: Dict[str, Student],
                 teachers: Dict[str, Teacher],
                 sections: Dict[str, Section],
                 periods: Dict[str, Period],
                 student_preferences: Dict[str, StudentPreference],
                 time_limit_seconds: int = 900):
        """
        Initialize the MILP optimizer.
        
        Args:
            students: Dictionary of Student objects by student ID
            teachers: Dictionary of Teacher objects by teacher ID
            sections: Dictionary of Section objects by section ID
            periods: Dictionary of Period objects by period ID
            student_preferences: Dictionary of StudentPreference objects by student ID
            time_limit_seconds: Maximum solution time in seconds (default: 15 minutes)
        """
        self.students = students
        self.teachers = teachers
        self.sections = sections
        self.periods = periods
        self.student_preferences = student_preferences
        self.time_limit_seconds = time_limit_seconds
        
        # Statistics and metrics
        self.stats = {
            'model_build_time': 0,
            'solution_time': 0,
            'obj_value': 0,
            'gap': 0.0,
            'sections_scheduled': 0,
            'students_assigned': 0,
            'total_assignments': 0,
            'preference_satisfaction': 0.0,
        }
        
        logger.info(f"Initialized MILP optimizer with:"
                    f" {len(students)} students,"
                    f" {len(teachers)} teachers,"
                    f" {len(sections)} sections,"
                    f" {len(periods)} periods")
    
    def build_model(self) -> gp.Model:
        """
        Build the MILP model with all variables, constraints, and objective function.
        
        Returns:
            Gurobi model ready for optimization
        """
        start_time = time.time()
        logger.info("Building MILP model...")
        
        # Create a new model
        model = gp.Model("school_scheduling")
        
        # Set model parameters
        model.setParam('TimeLimit', self.time_limit_seconds)
        model.setParam('MIPGap', 0.02)  # 2% MIP gap is acceptable
        model.setParam('Threads', 0)    # Use all available cores
        
        # Create decision variables
        
        # 1. Section to period assignment variables
        section_period = {}
        for section_id, section in self.sections.items():
            for period_id, period in self.periods.items():
                section_period[(section_id, period_id)] = model.addVar(
                    vtype=GRB.BINARY,
                    name=f"section_{section_id}_period_{period_id}"
                )
        
        # 2. Student to section assignment variables
        student_section = {}
        for student_id, student in self.students.items():
            # Only create variables for sections that match student preferences
            if student_id in self.student_preferences:
                preferred_courses = self.student_preferences[student_id].preferred_courses
                for section_id, section in self.sections.items():
                    if section.course_id in preferred_courses:
                        student_section[(student_id, section_id)] = model.addVar(
                            vtype=GRB.BINARY,
                            name=f"student_{student_id}_section_{section_id}"
                        )
        
        # Add constraints
        
        # 1. Each section can be assigned to at most one period
        for section_id in self.sections:
            model.addConstr(
                gp.quicksum(section_period[(section_id, period_id)] 
                           for period_id in self.periods) <= 1,
                name=f"section_{section_id}_assigned_once"
            )
        
        # 2. Teacher cannot teach multiple sections in the same period
        for period_id in self.periods:
            for teacher_id in self.teachers:
                teacher_sections = [section_id for section_id, section in self.sections.items()
                                  if section.teacher_id == teacher_id]
                if teacher_sections:  # If teacher has sections
                    model.addConstr(
                        gp.quicksum(section_period[(section_id, period_id)]
                                   for section_id in teacher_sections) <= 1,
                        name=f"teacher_{teacher_id}_period_{period_id}_no_overlap"
                    )
        
        # 3. Teacher unavailability constraints
        for teacher_id, teacher in self.teachers.items():
            if teacher.unavailable_periods:
                for period_id in teacher.unavailable_periods:
                    teacher_sections = [section_id for section_id, section in self.sections.items()
                                      if section.teacher_id == teacher_id]
                    for section_id in teacher_sections:
                        model.addConstr(
                            section_period[(section_id, period_id)] == 0,
                            name=f"teacher_{teacher_id}_unavailable_period_{period_id}"
                        )
        
        # 4. Student can only be assigned to a section if the section is scheduled
        for student_id, student in self.students.items():
            if student_id in self.student_preferences:
                preferred_courses = self.student_preferences[student_id].preferred_courses
                for section_id, section in self.sections.items():
                    if section.course_id in preferred_courses:
                        model.addConstr(
                            student_section[(student_id, section_id)] <= 
                            gp.quicksum(section_period[(section_id, period_id)]
                                      for period_id in self.periods),
                            name=f"student_{student_id}_section_{section_id}_scheduled"
                        )
        
        # 5. Student cannot be assigned to multiple sections in the same period
        for student_id in self.students:
            if student_id in self.student_preferences:
                for period_id in self.periods:
                    relevant_sections = []
                    preferred_courses = self.student_preferences[student_id].preferred_courses
                    for section_id, section in self.sections.items():
                        if section.course_id in preferred_courses:
                            relevant_sections.append(section_id)
                    
                    if relevant_sections:
                        model.addConstr(
                            gp.quicksum(student_section[(student_id, section_id)] * 
                                      section_period[(section_id, period_id)]
                                      for section_id in relevant_sections) <= 1,
                            name=f"student_{student_id}_period_{period_id}_no_overlap"
                        )
        
        # 6. Section capacity constraints
        for section_id, section in self.sections.items():
            potential_students = []
            for student_id, prefs in self.student_preferences.items():
                if section.course_id in prefs.preferred_courses:
                    potential_students.append(student_id)
            
            if potential_students:
                model.addConstr(
                    gp.quicksum(student_section[(student_id, section_id)]
                              for student_id in potential_students) <= section.capacity,
                    name=f"section_{section_id}_capacity"
                )
        
        # 7. Student must be assigned to at least one section
        for student_id, prefs in self.student_preferences.items():
            relevant_sections = []
            for section_id, section in self.sections.items():
                if section.course_id in prefs.preferred_courses:
                    relevant_sections.append(section_id)
            
            if relevant_sections:
                model.addConstr(
                    gp.quicksum(student_section[(student_id, section_id)]
                              for section_id in relevant_sections) >= 1,
                    name=f"student_{student_id}_min_assignment"
                )
        
        # Set objective function
        
        # Main components of the objective:
        # 1. Maximize number of scheduled sections
        # 2. Maximize student preferences satisfaction
        # 3. Balance section assignments
        
        section_scheduling_obj = gp.quicksum(
            section_period[(section_id, period_id)]
            for section_id in self.sections
            for period_id in self.periods
        )
        
        student_preference_obj = gp.quicksum(
            student_section[(student_id, section_id)]
            for student_id, prefs in self.student_preferences.items()
            for section_id, section in self.sections.items()
            if section.course_id in prefs.preferred_courses
        )
        
        # Set the objective with weights
        model.setObjective(
            10 * section_scheduling_obj + student_preference_obj,
            GRB.MAXIMIZE
        )
        
        # Record build time
        self.stats['model_build_time'] = time.time() - start_time
        logger.info(f"Model built in {self.stats['model_build_time']:.2f} seconds")
        
        # Log model size
        logger.info(f"Model has {model.NumVars} variables and {model.NumConstrs} constraints")
        
        return model
    
    def optimize(self) -> Schedule:
        """
        Build and solve the MILP model to create an optimized schedule.
        
        Returns:
            Optimized Schedule object with section and student assignments
        """
        total_start = time.time()
        logger.info("Starting MILP optimization...")
        
        # Build the model
        model = self.build_model()
        
        # Solve the model
        solution_start = time.time()
        model.optimize()
        self.stats['solution_time'] = time.time() - solution_start
        
        # Create schedule from results
        schedule = Schedule()
        
        # Check solution status
        if model.Status == GRB.OPTIMAL or model.Status == GRB.TIME_LIMIT:
            # Record statistics
            self.stats['obj_value'] = model.objVal
            self.stats['gap'] = model.MIPGap
            
            # Process section to period assignments
            for section_id, section in self.sections.items():
                section_copy = Section(
                    id=section.id,
                    course_id=section.course_id,
                    teacher_id=section.teacher_id,
                    capacity=section.capacity
                )
                
                # Find if this section was scheduled
                assigned_period = None
                for period_id in self.periods:
                    var_name = f"section_{section_id}_period_{period_id}"
                    var = model.getVarByName(var_name)
                    if var and var.x > 0.5:  # If the variable is set to 1
                        assigned_period = period_id
                        break
                
                # Set period if assigned
                if assigned_period:
                    section_copy.period_id = assigned_period
                    self.stats['sections_scheduled'] += 1
                
                # Add to schedule
                schedule.sections[section_id] = section_copy
            
            # Process student assignments
            student_count = set()
            for student_id, prefs in self.student_preferences.items():
                for section_id, section in self.sections.items():
                    if section.course_id in prefs.preferred_courses:
                        var_name = f"student_{student_id}_section_{section_id}"
                        var = model.getVarByName(var_name)
                        if var and var.x > 0.5:  # If the variable is set to 1
                            # Create assignment
                            assignment = Assignment(
                                student_id=student_id,
                                section_id=section_id
                            )
                            schedule.assignments.append(assignment)
                            student_count.add(student_id)
                            self.stats['total_assignments'] += 1
            
            self.stats['students_assigned'] = len(student_count)
            
            # Calculate preference satisfaction
            if len(self.student_preferences) > 0:
                self.stats['preference_satisfaction'] = (
                    self.stats['total_assignments'] / len(self.student_preferences)
                )
            
            logger.info(f"MILP optimization completed in {self.stats['solution_time']:.2f} seconds")
            logger.info(f"Scheduled {self.stats['sections_scheduled']} sections out of {len(self.sections)}")
            logger.info(f"Assigned {self.stats['students_assigned']} students out of {len(self.students)}")
            logger.info(f"Made {self.stats['total_assignments']} total assignments")
            
        else:
            logger.warning(f"Optimization failed with status: {model.Status}")
            
        # Return the complete schedule
        return schedule