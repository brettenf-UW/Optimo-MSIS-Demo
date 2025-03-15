"""
Mixed Integer Linear Programming Optimizer for School Scheduling.

This module provides an implementation of the MILP approach to school scheduling
using the Gurobi solver. It creates a comprehensive mathematical model that
accounts for all hard constraints and optimizes for soft preferences.

License key: ba446ea2-f2f6-4614-8e8f-aa378d1404b5
"""
import logging
import time
import os
import psutil
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
                 warm_start: Optional[Schedule] = None,
                 time_limit_seconds: int = 900):
        """
        Initialize the MILP optimizer.
        
        Args:
            students: Dictionary of Student objects by student ID
            teachers: Dictionary of Teacher objects by teacher ID
            sections: Dictionary of Section objects by section ID
            periods: Dictionary of Period objects by period ID
            student_preferences: Dictionary of StudentPreference objects by student ID
            warm_start: Optional Schedule object to use as a warm start (typically from greedy algorithm)
            time_limit_seconds: Maximum solution time in seconds (default: 15 minutes)
        """
        self.students = students
        self.teachers = teachers
        self.sections = sections
        self.periods = periods
        self.student_preferences = student_preferences
        self.warm_start = warm_start
        self.time_limit_seconds = time_limit_seconds
        
        # Define course period restrictions - simple straightforward definition
        self.course_period_restrictions = {
            'Medical Career': ['R1', 'G1'],
            'Heroes Teach': ['R2', 'G2']
            # Add any other course-specific restrictions here
        }
        
        # Log the actual period restrictions being used
        logger.info(f"Medical Career restricted to periods: {self.course_period_restrictions['Medical Career']}")
        logger.info(f"Heroes Teach restricted to periods: {self.course_period_restrictions['Heroes Teach']}")
        
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
                    f" {len(periods)} periods,"
                    f" {'using warm start' if warm_start else 'no warm start'}")
    
    def get_allowed_periods(self, course_id: str) -> List[str]:
        """
        Get allowed periods for a course based on restrictions.
        
        Args:
            course_id: The course ID to check for restrictions
            
        Returns:
            List of period IDs that are allowed for this course
        """
        return self.course_period_restrictions.get(course_id, list(self.periods.keys()))
    
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
        
        # Set model parameters exactly as specified
        model.setParam('TimeLimit', 3600)         # 1 hour time limit
        model.setParam('Threads', 0)              # Use all available cores
        model.setParam('Presolve', 1)             # Use standard presolve
        model.setParam('Method', 1)               # Use dual simplex for LP relaxations
        model.setParam('MIPFocus', 1)             # Focus on feasible solutions
        model.setParam('MIPGap', 0.10)            # 10% MIP gap tolerance
        
        # Memory usage settings
        total_ram_gb = psutil.virtual_memory().total / (1024 ** 3)  # RAM in GB
        model.setParam('MemLimit', int(total_ram_gb * 0.95) * 1024)  # Use 95% of available RAM (in MB)
        model.setParam('NodefileStart', 0.95)      # Start writing to disk at 95% memory usage
        
        # Set the directory for node file offloading
        node_dir = '/tmp/gurobi_nodefiles'
        os.makedirs(node_dir, exist_ok=True)  
        model.setParam('NodefileDir', node_dir)
        
        # Create decision variables
        
        # 1. Section to period assignment variables
        section_period = {}
        
        # First, handle special course sections with fixed periods
        for course, allowed_periods in self.course_period_restrictions.items():
            # Find all sections for this special course
            special_sections = [section_id for section_id, section in self.sections.items() 
                               if section.course_id == course]
            
            # For each special section, create variables only for allowed periods
            for section_id in special_sections:
                for period_id in allowed_periods:
                    if period_id in self.periods:
                        section_period[(section_id, period_id)] = model.addVar(
                            vtype=GRB.BINARY,
                            name=f"section_{section_id}_period_{period_id}"
                        )
                # Special sections must be assigned to exactly one of their allowed periods
                model.addConstr(
                    gp.quicksum(section_period[(section_id, period_id)] 
                               for period_id in allowed_periods if period_id in self.periods) == 1,
                    name=f"special_section_{section_id}_must_be_assigned"
                )
                logger.info(f"Added constraint: special section {section_id} ({course}) must be assigned to one of {allowed_periods}")
                
        # Then handle regular sections with all periods
        for section_id, section in self.sections.items():
            # Skip special sections we already handled
            if section.course_id in self.course_period_restrictions:
                continue
                
            # Regular sections can be assigned to any period
            for period_id in self.periods:
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
        
        # 3. Course request satisfaction variables (for soft constraints)
        missed_request = {}
        for student_id, student_pref in self.student_preferences.items():
            for course_id in student_pref.preferred_courses:
                missed_request[(student_id, course_id)] = model.addVar(
                    vtype=GRB.BINARY,
                    name=f"missed_{student_id}_{course_id}"
                )
                
        # 4. Section capacity violation variables (for soft constraints)
        capacity_violation = {}
        for section_id, section in self.sections.items():
            capacity_violation[section_id] = model.addVar(
                vtype=GRB.INTEGER,
                lb=0,
                name=f"capacity_violation_{section_id}"
            )
            
        # 5. Student-section-period variables (for linearized constraints)
        student_section_period = {}
        for student_id in self.students:
            if student_id in self.student_preferences:
                preferred_courses = self.student_preferences[student_id].preferred_courses
                for section_id, section in self.sections.items():
                    if section.course_id in preferred_courses:
                        for period_id in self.periods:
                            if (section_id, period_id) in section_period:
                                student_section_period[(student_id, section_id, period_id)] = model.addVar(
                                    vtype=GRB.BINARY,
                                    name=f"student_{student_id}_section_{section_id}_period_{period_id}"
                                )
        
        # Add constraints
        
        # 1. Each regular section can be assigned to at most one period
        # (special sections already have their constraint)
        for section_id, section in self.sections.items():
            # Skip special sections that we already constrained to exactly one period
            if section.course_id in self.course_period_restrictions:
                continue
                
            model.addConstr(
                gp.quicksum(section_period[(section_id, period_id)] 
                           for period_id in self.periods if (section_id, period_id) in section_period) <= 1,
                name=f"section_{section_id}_assigned_once"
            )
        
        # 2. Teacher cannot teach multiple sections in the same period
        for period_id in self.periods:
            for teacher_id in self.teachers:
                teacher_sections = [section_id for section_id, section in self.sections.items()
                                  if section.teacher_id == teacher_id]
                # Check which of these sections have variables for this period
                valid_sections = [
                    section_id for section_id in teacher_sections 
                    if (section_id, period_id) in section_period
                ]
                if valid_sections:  # Only add constraint if there are valid sections
                    model.addConstr(
                        gp.quicksum(section_period[(section_id, period_id)]
                                   for section_id in valid_sections) <= 1,
                        name=f"teacher_{teacher_id}_period_{period_id}_no_overlap"
                    )
        
        # 3. Teacher unavailability constraints
        for teacher_id, teacher in self.teachers.items():
            if teacher.unavailable_periods:
                for period_id in teacher.unavailable_periods:
                    teacher_sections = [section_id for section_id, section in self.sections.items()
                                      if section.teacher_id == teacher_id]
                    valid_sections = [
                        section_id for section_id in teacher_sections 
                        if (section_id, period_id) in section_period
                    ]
                    for section_id in valid_sections:
                        model.addConstr(
                            section_period[(section_id, period_id)] == 0,
                            name=f"teacher_{teacher_id}_unavailable_period_{period_id}"
                        )
        
        # 4. Student can only be assigned to a section if the section is scheduled
        for student_id, student in self.students.items():
            if student_id in self.student_preferences:
                preferred_courses = self.student_preferences[student_id].preferred_courses
                for section_id, section in self.sections.items():
                    if section.course_id in preferred_courses and (student_id, section_id) in student_section:
                        model.addConstr(
                            student_section[(student_id, section_id)] <= 
                            gp.quicksum(section_period[(section_id, period_id)]
                                      for period_id in self.periods if (section_id, period_id) in section_period),
                            name=f"student_{student_id}_section_{section_id}_scheduled"
                        )
        
        # 5. Student-section-period linking constraints (linearization)
        for student_id in self.students:
            if student_id in self.student_preferences:
                for section_id, section in self.sections.items():
                    if (student_id, section_id) in student_section:
                        for period_id in self.periods:
                            if (section_id, period_id) in section_period and (student_id, section_id, period_id) in student_section_period:
                                # 5a. y <= x: Student can only be in section-period if assigned to section
                                model.addConstr(
                                    student_section_period[(student_id, section_id, period_id)] <= student_section[(student_id, section_id)],
                                    name=f"link_xy_{student_id}_{section_id}_{period_id}"
                                )
                                
                                # 5b. y <= z: Student can only be in section-period if section is in that period
                                model.addConstr(
                                    student_section_period[(student_id, section_id, period_id)] <= section_period[(section_id, period_id)],
                                    name=f"link_yz_{student_id}_{section_id}_{period_id}"
                                )
                                
                                # 5c. y >= x + z - 1: Student must be in section-period if assigned to section and section is in period
                                model.addConstr(
                                    student_section_period[(student_id, section_id, period_id)] >= 
                                    student_section[(student_id, section_id)] + section_period[(section_id, period_id)] - 1,
                                    name=f"link_xyz_{student_id}_{section_id}_{period_id}"
                                )
        
        # 6. Student cannot be assigned to multiple sections in the same period (using linearized variables)
        for student_id in self.students:
            if student_id in self.student_preferences:
                for period_id in self.periods:
                    y_vars = [
                        student_section_period[(student_id, section_id, period_id)]
                        for section_id in self.sections
                        if (student_id, section_id, period_id) in student_section_period
                    ]
                    if y_vars:
                        model.addConstr(
                            gp.quicksum(y_vars) <= 1,
                            name=f"student_{student_id}_period_{period_id}_no_overlap"
                        )
        
        # 7. SPED student distribution constraints (max 12 SPED students per section)
        sped_students = [student_id for student_id, student in self.students.items() 
                         if hasattr(student, 'sped_status') and student.sped_status]
        if sped_students:  # Only if we have SPED students in the data
            for section_id in self.sections:
                potential_sped_students = []
                for student_id in sped_students:
                    if student_id in self.student_preferences:
                        prefs = self.student_preferences[student_id]
                        if (self.sections[section_id].course_id in prefs.preferred_courses and 
                            (student_id, section_id) in student_section):
                            potential_sped_students.append(student_id)
                
                if potential_sped_students:
                    model.addConstr(
                        gp.quicksum(student_section[(student_id, section_id)]
                                  for student_id in potential_sped_students) <= 12,
                        name=f"section_{section_id}_sped_limit"
                    )
        
        # 8. Section capacity constraints (SOFT)
        for section_id, section in self.sections.items():
            potential_students = []
            for student_id, prefs in self.student_preferences.items():
                if (section.course_id in prefs.preferred_courses and 
                    (student_id, section_id) in student_section):
                    potential_students.append(student_id)
            
            if potential_students:
                model.addConstr(
                    gp.quicksum(student_section[(student_id, section_id)]
                              for student_id in potential_students) <= 
                    section.capacity + capacity_violation[section_id],
                    name=f"section_{section_id}_soft_capacity"
                )
        
        # 9. Student course requirements (SOFT) - either student is assigned to a course or the missed request variable is 1
        for student_id, prefs in self.student_preferences.items():
            for course_id in prefs.preferred_courses:
                sections_for_course = [
                    section_id for section_id, section in self.sections.items()
                    if section.course_id == course_id and (student_id, section_id) in student_section
                ]
                
                if sections_for_course:
                    model.addConstr(
                        gp.quicksum(student_section[(student_id, section_id)]
                                  for section_id in sections_for_course) + 
                        missed_request[(student_id, course_id)] >= 1,
                        name=f"student_{student_id}_course_{course_id}_requirement"
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
            if (section_id, period_id) in section_period
        )
        
        student_preference_obj = gp.quicksum(
            student_section[(student_id, section_id)]
            for student_id, prefs in self.student_preferences.items()
            for section_id, section in self.sections.items()
            if section.course_id in prefs.preferred_courses and (student_id, section_id) in student_section
        )
        
        # Penalties for soft constraints
        missed_request_penalty = gp.quicksum(
            1000 * missed_request[(student_id, course_id)]  # High weight to minimize missed requests
            for student_id, prefs in self.student_preferences.items()
            for course_id in prefs.preferred_courses
        )
        
        capacity_penalty = gp.quicksum(
            capacity_violation[section_id]  # Weight of 1 for capacity violations
            for section_id in self.sections
        )
        
        # Set the objective to maximize assignments while minimizing penalties
        model.setObjective(
            10 * section_scheduling_obj + student_preference_obj - missed_request_penalty - capacity_penalty,
            GRB.MAXIMIZE
        )
        
        # Apply warm start and heuristic guidance if available
        if self.warm_start:
            logger.info("Applying greedy solution as warm start and heuristic")
            
            # Use slightly relaxed tolerances for warm start feasibility
            model.setParam('FeasibilityTol', 1e-5) # Slightly relaxed tolerance for feasibility
            model.setParam('IntFeasTol', 1e-5)   # Slightly relaxed tolerance for integer feasibility
            
            try:
                # Set initial section-period assignments from warm start ONLY if consistent with constraints
                for section_id, section in self.warm_start.sections.items():
                    if section.is_scheduled and section_id in self.sections:
                        period_id = section.period_id
                        course_id = self.sections[section_id].course_id
                        
                        # Validate warm start - skip if it violates constraints
                        valid_warm_start = True
                        
                        # Skip if section doesn't exist in current data
                        if section_id not in self.sections:
                            logger.warning(f"Skipping warm start: section {section_id} not found in current data")
                            valid_warm_start = False
                            
                        # Check special course period restrictions
                        if course_id in self.course_period_restrictions:
                            allowed_periods = self.course_period_restrictions[course_id]
                            if period_id not in allowed_periods:
                                logger.warning(f"Skipping warm start: section {section_id} ({course_id}) can't be in period {period_id}")
                                logger.warning(f"Allowed periods are: {allowed_periods}")
                                valid_warm_start = False
                                
                        # Check teacher conflicts
                        teacher_id = self.sections[section_id].teacher_id
                        for other_id, other_section in self.warm_start.sections.items():
                            if (other_id != section_id and 
                                other_section.is_scheduled and 
                                other_section.period_id == period_id and
                                other_id in self.sections and
                                self.sections[other_id].teacher_id == teacher_id):
                                logger.warning(f"Skipping warm start: teacher {teacher_id} has conflict in period {period_id}")
                                valid_warm_start = False
                                break
                                
                        # Only use warm start values that satisfy all constraints
                        if not valid_warm_start:
                            continue
                            
                        if (section_id, period_id) in section_period:
                            try:
                                # Both set Start (for warm start) and set obj coefficient (for heuristic guidance)
                                section_period[(section_id, period_id)].Start = 1.0
                                # Slightly increase the objective coefficient to encourage using this assignment
                                model.chgCoeff(model.getObjective(), section_period[(section_id, period_id)], 11)  
                                logger.debug(f"Warm start: section {section_id} assigned to period {period_id}")
                            except Exception as e:
                                logger.warning(f"Failed to set warm start for section {section_id} in period {period_id}: {str(e)}")
                                
                # Set initial student-section assignments from warm start
                for assignment in self.warm_start.assignments:
                    student_id = assignment.student_id
                    section_id = assignment.section_id
                    if (student_id, section_id) in student_section:
                        try:
                            student_section[(student_id, section_id)].Start = 1.0
                            # Slightly increase the objective coefficient for this assignment
                            model.chgCoeff(model.getObjective(), student_section[(student_id, section_id)], 1.2)
                        except Exception as e:
                            logger.warning(f"Failed to set warm start for student {student_id} in section {section_id}: {str(e)}")
            except Exception as e:
                logger.warning(f"Error applying warm start: {str(e)}. Continuing without warm start.")
            
            # Just update the model to use warm start values - don't use heuristic callback
            # This will only use the warm start for initialization and presolve
            model.update()
            logger.info("Applied warm start values for presolve only (no heuristic callbacks)")
            
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
        
        # Solve the model with error handling
        solution_start = time.time()
        try:
            # Just optimize - no callbacks (use warm start only for presolve)
            model.optimize()
        except Exception as e:
            logger.error(f"Error during MILP optimization: {str(e)}")
            # Create an empty schedule and return it - pipeline will fall back to greedy
            logger.info("Returning empty schedule due to optimization error")
            return Schedule()
            
        self.stats['solution_time'] = time.time() - solution_start
        
        # Log the model status
        status_name = "UNKNOWN"
        if hasattr(GRB, "STATUS_CODES") and model.Status in GRB.STATUS_CODES:
            status_name = GRB.STATUS_CODES[model.Status]
        logger.info(f"Optimization complete with status: {model.Status} ({status_name})")
        
        # Create schedule from results
        schedule = Schedule()
        
        # Process results if we have a valid solution
        if model.Status in [GRB.OPTIMAL, GRB.TIME_LIMIT, GRB.SOLUTION_LIMIT, GRB.INTERRUPTED, GRB.SUBOPTIMAL]:
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