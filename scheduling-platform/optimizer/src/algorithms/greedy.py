"""
Greedy algorithm implementation for school schedule optimization.
This module provides a fast approach to generate a workable schedule.
"""
import pandas as pd
import numpy as np
from collections import defaultdict, Counter
import logging
from typing import Dict, List, Set, Tuple, Any, Optional
from ..models.entities import Schedule, Section, Student, Teacher, Period, StudentPreference, Assignment
import time

# Configure logger
logger = logging.getLogger(__name__)


class GreedyOptimizer:
    """
    Implements a greedy algorithm for schedule optimization.
    
    The algorithm works in two main phases:
    1. Schedule sections to periods based on constraints and priorities
    2. Assign students to sections based on preferences and constraints
    """
    
    def __init__(self, 
                 students: Dict[str, Student],
                 teachers: Dict[str, Teacher],
                 sections: Dict[str, Section],
                 periods: Dict[str, Period],
                 student_preferences: Dict[str, StudentPreference]):
        """
        Initialize the optimizer with the necessary data.
        
        Args:
            students: Dictionary of Student objects
            teachers: Dictionary of Teacher objects
            sections: Dictionary of Section objects
            periods: Dictionary of Period objects
            student_preferences: Dictionary of StudentPreference objects
        """
        self.students = students
        self.teachers = teachers
        self.sections = sections
        self.periods = periods
        self.student_preferences = student_preferences
        
        # Preprocessed data for optimization
        self.course_to_sections = defaultdict(list)
        self.teacher_to_sections = defaultdict(list)
        self.section_to_course = {}
        self.section_to_teacher = {}
        self.section_to_dept = {}
        self.special_course_periods = {
            'Medical Career': [p.id for p in periods.values() if p.name in ['R1', 'G1']],
            'Heroes Teach': [p.id for p in periods.values() if p.name in ['R2', 'G2']]
        }
        self.sped_students = {s_id for s_id, s in students.items() if s.has_special_needs}
        
        # Schedule tracking
        self.scheduled_sections = {}  # section_id -> period_id
        self.student_assignments = defaultdict(list)  # student_id -> [section_id, ...]
        
        # Preprocess data
        self._preprocess_data()
        
    def _preprocess_data(self) -> None:
        """
        Preprocess data to create useful mappings for optimization.
        """
        logger.info("Preprocessing data for greedy optimization")
        
        # Map courses to sections
        for section_id, section in self.sections.items():
            self.course_to_sections[section.course_id].append(section_id)
            self.section_to_course[section_id] = section.course_id
            
            if section.teacher_id:
                self.teacher_to_sections[section.teacher_id].append(section_id)
                self.section_to_teacher[section_id] = section.teacher_id
                
    def _compute_section_priority(self) -> Dict[str, float]:
        """
        Compute priority scores for sections to determine scheduling order.
        Higher score = higher priority (schedule earlier).
        
        Returns:
            Dictionary mapping section IDs to priority scores
        """
        section_priority = {}
        
        for section_id, section in self.sections.items():
            course_id = section.course_id
            teacher_id = section.teacher_id
            
            # Base priority score
            priority = 1.0
            
            # Special course sections have highest priority
            if course_id in self.special_course_periods:
                priority *= 5.0
            
            # Sports Med sections have high priority
            if course_id == 'Sports Med':
                priority *= 3.0
            
            # Give higher priority to sections with teacher constraints
            if teacher_id and teacher_id in self.teachers:
                teacher = self.teachers[teacher_id]
                
                # Teachers with many unavailable periods are harder to schedule
                unavail_count = len(teacher.unavailable_periods)
                priority *= (1.0 + 0.1 * unavail_count)
                
                # Teachers with many sections are harder to schedule
                teacher_section_count = len(self.teacher_to_sections[teacher_id])
                priority *= (1.0 + 0.2 * teacher_section_count)
            
            # Courses with fewer sections are harder to schedule
            course_section_count = len(self.course_to_sections[course_id])
            priority *= (1.0 + 1.0 / course_section_count)
            
            # Student demand-based priority
            student_demand = 0
            for pref in self.student_preferences.values():
                if course_id in pref.preferred_courses:
                    student_demand += 1
            
            priority *= (1.0 + 0.001 * student_demand)
            
            section_priority[section_id] = priority
            
        return section_priority
    
    def _compute_period_score(self, section_id: str, period_id: str) -> float:
        """
        Compute how good a period is for a given section.
        Higher score = better period assignment.
        
        Args:
            section_id: Section ID
            period_id: Period ID
            
        Returns:
            Score for assigning the section to this period
        """
        course_id = self.section_to_course[section_id]
        teacher_id = self.section_to_teacher.get(section_id)
        
        # Start with base score
        score = 1.0
        
        # Special course period restrictions
        if course_id in self.special_course_periods:
            if period_id not in self.special_course_periods[course_id]:
                return 0.0  # Forbidden period
            
            # If this is a required period and course has no section in it yet, boost score
            course_sections = self.course_to_sections[course_id]
            period_used = any(s in self.scheduled_sections and 
                            self.scheduled_sections[s] == period_id
                            for s in course_sections)
            if not period_used:
                score *= 2.0  # Boost score for required periods not yet used
        
        # Check teacher unavailability
        if teacher_id and teacher_id in self.teachers:
            teacher = self.teachers[teacher_id]
            if period_id in teacher.unavailable_periods:
                return 0.0  # Unavailable period
            
            # Check teacher conflicts - teacher can't teach two sections in same period
            for other_section in self.teacher_to_sections[teacher_id]:
                if (other_section in self.scheduled_sections and 
                    self.scheduled_sections[other_section] == period_id):
                    return 0.0  # Teacher conflict
        
        # Prefer balanced distribution of course sections across periods
        course_sections = self.course_to_sections[course_id]
        course_period_usage = Counter([self.scheduled_sections[s] 
                                     for s in course_sections 
                                     if s in self.scheduled_sections])
        
        if period_id in course_period_usage:
            score /= (1.0 + 0.5 * course_period_usage[period_id])  # Lower score if period already has this course
        
        # Sports Med constraint: avoid multiple Sports Med sections in same period
        if course_id == 'Sports Med':
            sports_med_sections = [s for s, c in self.section_to_course.items() if c == 'Sports Med']
            sports_med_period_usage = sum(1 for s in sports_med_sections 
                                        if s in self.scheduled_sections and 
                                        self.scheduled_sections[s] == period_id)
            
            if sports_med_period_usage > 0:
                score *= 0.5  # Lower score if period already has Sports Med section
        
        # Balancing consideration: prefer periods with fewer sections overall
        period_usage = sum(1 for p in self.scheduled_sections.values() if p == period_id)
        score /= (1.0 + 0.1 * period_usage)
        
        return score
    
    def _schedule_sections(self) -> None:
        """
        Schedule sections to periods using a greedy approach.
        Prioritizes difficult-to-schedule sections first.
        """
        logger.info("Starting section scheduling with greedy algorithm")
        
        # Compute section priorities
        section_priority = self._compute_section_priority()
        
        # Sort sections by priority (highest first)
        sorted_sections = sorted(self.sections.keys(), 
                               key=lambda s: -section_priority.get(s, 0))
        
        # Sort periods by name for consistency
        sorted_periods = sorted(self.periods.keys())
        
        # First phase: Schedule special course sections
        for section_id in sorted_sections:
            course_id = self.section_to_course[section_id]
            if course_id in self.special_course_periods:
                best_period = None
                best_score = -1
                
                for period_id in sorted_periods:
                    score = self._compute_period_score(section_id, period_id)
                    if score > best_score:
                        best_period = period_id
                        best_score = score
                
                if best_period and best_score > 0:
                    self.scheduled_sections[section_id] = best_period
                    logger.info(f"Scheduled special section {section_id} ({course_id}) to period {best_period}")
        
        # Second phase: Schedule Sports Med sections
        for section_id in sorted_sections:
            if section_id in self.scheduled_sections:
                continue  # Already scheduled
                
            course_id = self.section_to_course[section_id]
            if course_id == 'Sports Med':
                best_period = None
                best_score = -1
                
                for period_id in sorted_periods:
                    score = self._compute_period_score(section_id, period_id)
                    if score > best_score:
                        best_period = period_id
                        best_score = score
                
                if best_period and best_score > 0:
                    self.scheduled_sections[section_id] = best_period
                    logger.info(f"Scheduled Sports Med section {section_id} to period {best_period}")
        
        # Third phase: Schedule remaining sections
        for section_id in sorted_sections:
            if section_id in self.scheduled_sections:
                continue  # Already scheduled
            
            best_period = None
            best_score = -1
            
            for period_id in sorted_periods:
                score = self._compute_period_score(section_id, period_id)
                if score > best_score:
                    best_period = period_id
                    best_score = score
            
            if best_period and best_score > 0:
                self.scheduled_sections[section_id] = best_period
                logger.info(f"Scheduled section {section_id} to period {best_period}")
            else:
                logger.warning(f"Could not schedule section {section_id}")
    
    def _compute_student_section_score(self, student_id: str, section_id: str) -> float:
        """
        Compute score for assigning a student to a section.
        Higher score = better assignment.
        
        Args:
            student_id: Student ID
            section_id: Section ID
        
        Returns:
            Score for assigning student to section
        """
        # Check if section is scheduled
        if section_id not in self.scheduled_sections:
            return 0.0  # Section not scheduled
        
        period_id = self.scheduled_sections[section_id]
        section = self.sections[section_id]
        course_id = section.course_id
        
        # Check if student already assigned to this course
        student_courses = [self.section_to_course[sec] 
                         for sec in self.student_assignments.get(student_id, [])]
        
        if course_id in student_courses:
            return 0.0  # Already assigned to this course
        
        # Check if student wants this course
        student_pref = self.student_preferences.get(student_id)
        if not student_pref or course_id not in student_pref.preferred_courses:
            return 0.0  # Not preferred
        
        # Check for period conflicts
        student_periods = [self.scheduled_sections.get(sec) 
                         for sec in self.student_assignments.get(student_id, [])]
        
        if period_id in student_periods:
            return 0.0  # Period conflict
        
        # Check section capacity
        section_students = [s for s, secs in self.student_assignments.items() if section_id in secs]
        if len(section_students) >= section.capacity:
            return 0.0  # Section full
        
        # Base score
        score = 1.0
        
        # Favor less filled sections
        fill_ratio = len(section_students) / section.capacity
        score *= (1.1 - fill_ratio)  # Higher score for less filled sections
        
        # SPED distribution - soft constraint
        if student_id in self.sped_students:
            sped_count = sum(1 for s in section_students if s in self.sped_students)
            if sped_count >= 2:  # Avoid more than 2 SPED students per section
                score *= (0.5 ** (sped_count - 1))  # Exponential penalty
        
        # Boost score for required courses
        if student_pref and student_pref.is_required(course_id):
            score *= 2.0
        
        # Boost score for courses that might fill up quickly
        remaining_sections = [s for s in self.course_to_sections.get(course_id, []) 
                            if s in self.scheduled_sections and 
                            len([st for st, secs in self.student_assignments.items() 
                                if s in secs]) < self.sections[s].capacity]
        
        if len(remaining_sections) <= 2:  # Few options left
            score *= 2.0  # Boost score
        
        return score
    
    def _assign_students(self) -> None:
        """
        Assign students to sections greedily based on preferences and constraints.
        """
        logger.info("Starting student assignment with greedy algorithm")
        
        # Calculate student "hardness" to prioritize difficult students first
        student_hardness = {}
        
        for student_id, student in self.students.items():
            # Base hardness
            hardness = 1.0
            
            # SPED students are harder to place
            if student.has_special_needs:
                hardness *= 2.0
            
            # Students with special courses are harder to place
            student_pref = self.student_preferences.get(student_id)
            if student_pref:
                if any(c in ['Medical Career', 'Heroes Teach'] 
                    for c in student_pref.preferred_courses):
                    hardness *= 1.5
                
                # Students with many course preferences are harder to place
                num_courses = len(student_pref.preferred_courses)
                hardness *= (1.0 + 0.1 * num_courses)
                
                # Students with many required courses are harder to place
                num_required = len(student_pref.required_courses)
                hardness *= (1.0 + 0.2 * num_required)
            
            student_hardness[student_id] = hardness
        
        # Sort students by hardness (hardest first)
        sorted_students = sorted(self.students.keys(), 
                               key=lambda s: -student_hardness.get(s, 0))
        
        # First phase: Assign special courses
        special_courses = ['Medical Career', 'Heroes Teach', 'Sports Med']
        for student_id in sorted_students:
            student_pref = self.student_preferences.get(student_id)
            if not student_pref:
                continue
                
            for course_id in special_courses:
                if course_id not in student_pref.preferred_courses:
                    continue  # Student doesn't want this course
                
                # Get available sections for this course
                available_sections = []
                for section_id in self.course_to_sections.get(course_id, []):
                    if section_id not in self.scheduled_sections:
                        continue  # Section not scheduled
                    
                    score = self._compute_student_section_score(student_id, section_id)
                    if score > 0:
                        available_sections.append((section_id, score))
                
                if available_sections:
                    # Choose best section
                    best_section = max(available_sections, key=lambda x: x[1])[0]
                    self.student_assignments[student_id].append(best_section)
                    logger.info(f"Assigned student {student_id} to special section {best_section} ({course_id})")
        
        # Second phase: Assign non-special courses
        for student_id in sorted_students:
            student_pref = self.student_preferences.get(student_id)
            if not student_pref:
                continue
                
            # Calculate which courses student still needs
            assigned_courses = [self.section_to_course[sec] 
                              for sec in self.student_assignments.get(student_id, [])]
            
            needed_courses = [c for c in student_pref.preferred_courses 
                            if c not in assigned_courses and c not in special_courses]
            
            # Dictionary to track best section for each needed course
            best_sections = {}
            
            # Find best section for each needed course
            for course_id in needed_courses:
                best_section = None
                best_score = 0
                
                for section_id in self.course_to_sections.get(course_id, []):
                    if section_id not in self.scheduled_sections:
                        continue  # Section not scheduled
                    
                    score = self._compute_student_section_score(student_id, section_id)
                    if score > best_score:
                        best_section = section_id
                        best_score = score
                
                if best_section:
                    best_sections[course_id] = (best_section, best_score)
            
            # Sort needed courses by score (best first)
            sorted_courses = sorted(best_sections.keys(), key=lambda c: -best_sections[c][1])
            
            # Assign student to each course in order
            for course_id in sorted_courses:
                section_id = best_sections[course_id][0]
                
                # Check if still valid (no period conflicts)
                score = self._compute_student_section_score(student_id, section_id)
                if score > 0:
                    self.student_assignments[student_id].append(section_id)
                    logger.info(f"Assigned student {student_id} to section {section_id} ({course_id})")
    
    def optimize(self) -> Schedule:
        """
        Run the greedy optimization process.
        
        Returns:
            Schedule object containing the optimized schedule
        """
        start_time = time.time()
        logger.info("Starting greedy optimization")
        
        # Schedule sections to periods
        self._schedule_sections()
        
        # Assign students to sections
        self._assign_students()
        
        # Build the resulting schedule
        result_sections = {}
        for section_id, section in self.sections.items():
            # Create a new section object with updated period
            new_section = Section(
                id=section.id,
                course_id=section.course_id,
                teacher_id=section.teacher_id,
                period_id=self.scheduled_sections.get(section_id),
                capacity=section.capacity,
                room=section.room
            )
            result_sections[section_id] = new_section
        
        # Build assignments set
        assignments = set()
        for student_id, section_ids in self.student_assignments.items():
            for section_id in section_ids:
                assignments.add(Assignment(student_id=student_id, section_id=section_id))
        
        # Create final schedule
        schedule = Schedule(sections=result_sections, assignments=assignments)
        
        # Log statistics
        section_count = len(self.scheduled_sections)
        total_sections = len(self.sections)
        
        total_assignments = sum(len(sections) for sections in self.student_assignments.values())
        total_requests = sum(len(pref.preferred_courses) for pref in self.student_preferences.values())
        
        logger.info(f"Scheduled {section_count}/{total_sections} sections ({section_count/total_sections:.1%})")
        logger.info(f"Satisfied {total_assignments}/{total_requests} course requests ({total_assignments/total_requests:.1%})")
        logger.info(f"Greedy optimization completed in {time.time() - start_time:.2f} seconds")
        
        return schedule