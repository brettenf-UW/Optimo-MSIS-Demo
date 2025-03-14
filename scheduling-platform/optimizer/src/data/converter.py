"""
Data converter module.

Handles conversions between different data formats:
- DataFrame to domain objects
- Domain objects to DataFrame
- CSV data to domain objects
"""
import pandas as pd
from datetime import time
from typing import Dict, List, Set, Tuple, Any, Optional
import logging
from collections import defaultdict
from ..models.entities import (
    Student, Teacher, Period, Section, Course, 
    StudentPreference, Schedule, Assignment
)

logger = logging.getLogger(__name__)


class DataConverter:
    """
    Converts between different data representations used in the system.
    
    Responsibilities:
    - Convert CSV/DataFrame data to domain model objects
    - Convert domain model objects back to DataFrames for output
    - Generate reports from model data
    """
    
    @staticmethod
    def convert_periods(periods_df: pd.DataFrame) -> Dict[str, Period]:
        """
        Convert periods DataFrame to Period objects.
        
        Args:
            periods_df: DataFrame containing period data
            
        Returns:
            Dictionary mapping period IDs to Period objects
        """
        periods = {}
        
        for _, row in periods_df.iterrows():
            # Parse time values - handle different format possibilities
            try:
                if isinstance(row.get('Start Time'), str):
                    start_time = time.fromisoformat(row['Start Time'])
                else:
                    # Default values if missing
                    start_time = time(8, 0)
                
                if isinstance(row.get('End Time'), str):
                    end_time = time.fromisoformat(row['End Time'])
                else:
                    # Default values if missing
                    end_time = time(9, 0)
            except ValueError:
                # Fallback if time format is incorrect
                logger.warning(f"Invalid time format for period {row.get('Period ID', 'Unknown')}")
                start_time = time(8, 0)
                end_time = time(9, 0)
            
            # Default day if not specified
            day_of_week = int(row.get('Day of Week', 0))
            
            # Make sure day is in valid range
            if day_of_week < 0 or day_of_week > 6:
                day_of_week = 0
            
            period = Period(
                id=str(row.get('Period ID', row.get('period_name', f"P{_}"))),
                name=str(row.get('Period Name', row.get('period_name', f"Period {_}"))),
                start_time=start_time,
                end_time=end_time,
                day_of_week=day_of_week
            )
            
            periods[period.id] = period
            
        return periods
    
    @staticmethod
    def convert_students(students_df: pd.DataFrame) -> Dict[str, Student]:
        """
        Convert students DataFrame to Student objects.
        
        Args:
            students_df: DataFrame containing student data
            
        Returns:
            Dictionary mapping student IDs to Student objects
        """
        students = {}
        
        for _, row in students_df.iterrows():
            # Check for special needs
            has_special_needs = False
            if 'SPED' in row:
                has_special_needs = str(row['SPED']).lower() in ['yes', 'true', '1', 'y']
            
            student = Student(
                id=str(row['Student ID']),
                first_name=str(row.get('First Name', '')),
                last_name=str(row.get('Last Name', '')),
                email=str(row.get('Email', f"{row['Student ID']}@school.edu")),
                grade_level=int(row.get('Grade Level', 0)),
                has_special_needs=has_special_needs
            )
            
            students[student.id] = student
            
        return students
    
    @staticmethod
    def convert_teachers(teachers_df: pd.DataFrame, 
                        unavailability_df: Optional[pd.DataFrame] = None) -> Dict[str, Teacher]:
        """
        Convert teachers DataFrame to Teacher objects.
        
        Args:
            teachers_df: DataFrame containing teacher data
            unavailability_df: Optional DataFrame containing teacher unavailability data
            
        Returns:
            Dictionary mapping teacher IDs to Teacher objects
        """
        teachers = {}
        
        # Create unavailability mapping
        unavailable_periods = defaultdict(set)
        if unavailability_df is not None:
            for _, row in unavailability_df.iterrows():
                teacher_id = str(row['Teacher ID'])
                if pd.notna(row.get('Unavailable Periods', '')):
                    periods = str(row['Unavailable Periods']).split(',')
                    for period in periods:
                        unavailable_periods[teacher_id].add(period.strip())
        
        for _, row in teachers_df.iterrows():
            teacher_id = str(row['Teacher ID'])
            
            teacher = Teacher(
                id=teacher_id,
                first_name=str(row.get('First Name', '')),
                last_name=str(row.get('Last Name', '')),
                email=str(row.get('Email', f"{teacher_id}@school.edu")),
                department=str(row.get('Department', '')),
                max_sections=int(row.get('Max Sections', 5)),
                unavailable_periods=unavailable_periods.get(teacher_id, set())
            )
            
            teachers[teacher.id] = teacher
            
        return teachers
    
    @staticmethod
    def convert_sections(sections_df: pd.DataFrame) -> Dict[str, Section]:
        """
        Convert sections DataFrame to Section objects.
        
        Args:
            sections_df: DataFrame containing section data
            
        Returns:
            Dictionary mapping section IDs to Section objects
        """
        sections = {}
        
        for _, row in sections_df.iterrows():
            section = Section(
                id=str(row['Section ID']),
                course_id=str(row['Course ID']),
                teacher_id=str(row.get('Teacher Assigned', '')),
                period_id=str(row.get('Period', '')),
                capacity=int(row.get('# of Seats Available', 30)),
                room=str(row.get('Room', ''))
            )
            
            sections[section.id] = section
            
        return sections
    
    @staticmethod
    def convert_preferences(preferences_df: pd.DataFrame) -> Dict[str, StudentPreference]:
        """
        Convert student preferences DataFrame to StudentPreference objects.
        
        Args:
            preferences_df: DataFrame containing student preference data
            
        Returns:
            Dictionary mapping student IDs to StudentPreference objects
        """
        preferences = {}
        
        for _, row in preferences_df.iterrows():
            student_id = str(row['Student ID'])
            
            # Parse preferred courses
            preferred_courses = []
            if pd.notna(row.get('Preferred Sections', '')):
                preferred_courses = [c.strip() for c in str(row['Preferred Sections']).split(';')]
            
            # Parse required courses (if available)
            required_courses = []
            if 'Required Sections' in row and pd.notna(row.get('Required Sections', '')):
                required_courses = [c.strip() for c in str(row['Required Sections']).split(';')]
            
            preference = StudentPreference(
                student_id=student_id,
                preferred_courses=preferred_courses,
                required_courses=required_courses
            )
            
            preferences[student_id] = preference
            
        return preferences
    
    @staticmethod
    def convert_to_master_schedule_df(schedule: Schedule) -> pd.DataFrame:
        """
        Convert a Schedule object to a master schedule DataFrame.
        
        Args:
            schedule: Schedule object
            
        Returns:
            DataFrame with columns: Section ID, Course ID, Teacher ID, Period, Capacity
        """
        master_schedule = []
        
        for section_id, section in schedule.sections.items():
            master_schedule.append({
                'Section ID': section_id,
                'Course ID': section.course_id,
                'Teacher ID': section.teacher_id if section.teacher_id else "Unassigned",
                'Period': section.period_id if section.period_id else "Unscheduled",
                'Capacity': section.capacity,
                'Room': section.room if section.room else ""
            })
        
        return pd.DataFrame(master_schedule)
    
    @staticmethod
    def convert_to_student_assignments_df(schedule: Schedule) -> pd.DataFrame:
        """
        Convert a Schedule object to a student assignments DataFrame.
        
        Args:
            schedule: Schedule object
            
        Returns:
            DataFrame with columns: Student ID, Section ID
        """
        student_assignments = []
        
        for assignment in schedule.assignments:
            student_assignments.append({
                'Student ID': assignment.student_id,
                'Section ID': assignment.section_id
            })
        
        return pd.DataFrame(student_assignments)
    
    @staticmethod
    def convert_to_teacher_schedule_df(schedule: Schedule) -> pd.DataFrame:
        """
        Convert a Schedule object to a teacher schedule DataFrame.
        
        Args:
            schedule: Schedule object
            
        Returns:
            DataFrame with columns: Teacher ID, Section ID, Course ID, Period
        """
        teacher_schedule = []
        
        for section_id, section in schedule.sections.items():
            if section.teacher_id and section.period_id:
                teacher_schedule.append({
                    'Teacher ID': section.teacher_id,
                    'Section ID': section_id,
                    'Course ID': section.course_id,
                    'Period': section.period_id
                })
        
        return pd.DataFrame(teacher_schedule)
    
    @staticmethod
    def generate_utilization_report(schedule: Schedule) -> pd.DataFrame:
        """
        Generate a report on section utilization.
        
        Args:
            schedule: Schedule object
            
        Returns:
            DataFrame with utilization metrics
        """
        section_utilization = []
        
        for section_id, section in schedule.sections.items():
            enrollment = schedule.get_enrollment_count(section_id)
            utilization = enrollment / section.capacity if section.capacity > 0 else 0
            
            section_utilization.append({
                'Section ID': section_id,
                'Course ID': section.course_id,
                'Capacity': section.capacity,
                'Enrollment': enrollment,
                'Utilization': utilization,
                'Status': 'Low' if utilization < 0.3 else 
                        'High' if utilization > 0.9 else 'Good'
            })
        
        return pd.DataFrame(section_utilization)


# This import was moved to the top of the file