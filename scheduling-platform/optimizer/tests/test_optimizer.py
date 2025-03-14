"""
Tests for the optimizer module.
"""
import os
import pytest
import pandas as pd
import tempfile
import shutil
from pathlib import Path

from src.optimizer import ScheduleOptimizer
from src.data.loader import ScheduleDataLoader
from src.data.converter import DataConverter
from src.models.entities import Schedule, Student, Teacher, Period, Section, StudentPreference, Assignment
from src.algorithms.greedy import GreedyOptimizer


class TestScheduleOptimizer:
    """Test the ScheduleOptimizer class."""
    
    @pytest.fixture
    def test_data_dir(self):
        """Create a temporary directory with test data."""
        # Create a temporary directory
        temp_dir = tempfile.mkdtemp()
        
        # Create test data files
        self.create_test_data(temp_dir)
        
        yield temp_dir
        
        # Clean up
        shutil.rmtree(temp_dir)
    
    @pytest.fixture
    def output_dir(self):
        """Create a temporary directory for output files."""
        # Create a temporary directory
        temp_dir = tempfile.mkdtemp()
        
        yield temp_dir
        
        # Clean up
        shutil.rmtree(temp_dir)
    
    def create_test_data(self, directory):
        """Create test data files in the specified directory."""
        # Create students data
        students_df = pd.DataFrame({
            'Student ID': ['S001', 'S002', 'S003', 'S004', 'S005'],
            'First Name': ['John', 'Jane', 'Bob', 'Alice', 'Charlie'],
            'Last Name': ['Doe', 'Smith', 'Johnson', 'Brown', 'Wilson'],
            'Email': ['jdoe@school.edu', 'jsmith@school.edu', 'bjohnson@school.edu', 
                     'abrown@school.edu', 'cwilson@school.edu'],
            'Grade Level': [9, 10, 11, 9, 10],
            'SPED': ['No', 'Yes', 'No', 'No', 'Yes']
        })
        
        # Create teachers data
        teachers_df = pd.DataFrame({
            'Teacher ID': ['T001', 'T002', 'T003'],
            'First Name': ['David', 'Sarah', 'Michael'],
            'Last Name': ['Jones', 'Davis', 'Miller'],
            'Email': ['djones@school.edu', 'sdavis@school.edu', 'mmiller@school.edu'],
            'Department': ['Math', 'Science', 'English']
        })
        
        # Create sections data
        sections_df = pd.DataFrame({
            'Section ID': ['SEC001', 'SEC002', 'SEC003', 'SEC004', 'SEC005'],
            'Course ID': ['MATH101', 'SCI101', 'ENG101', 'MATH101', 'SCI101'],
            'Teacher Assigned': ['T001', 'T002', 'T003', 'T001', 'T002'],
            '# of Seats Available': [30, 25, 30, 30, 25],
            'Department': ['Math', 'Science', 'English', 'Math', 'Science']
        })
        
        # Create periods data
        periods_df = pd.DataFrame({
            'period_name': ['P1', 'P2', 'P3', 'P4', 'P5', 'P6', 'P7', 'P8'],
            'Start Time': ['08:00', '09:00', '10:00', '11:00', '13:00', '14:00', '15:00', '16:00'],
            'End Time': ['09:00', '10:00', '11:00', '12:00', '14:00', '15:00', '16:00', '17:00'],
            'Day of Week': [0, 0, 0, 0, 0, 0, 0, 0]
        })
        
        # Create student preferences data
        preferences_df = pd.DataFrame({
            'Student ID': ['S001', 'S002', 'S003', 'S004', 'S005'],
            'Preferred Sections': ['MATH101;SCI101', 'SCI101;ENG101', 'MATH101;ENG101', 
                                'MATH101;SCI101;ENG101', 'SCI101;ENG101']
        })
        
        # Create teacher unavailability data
        unavailability_df = pd.DataFrame({
            'Teacher ID': ['T001', 'T002', 'T003'],
            'Unavailable Periods': ['P1,P2', 'P3,P4', 'P5,P6']
        })
        
        # Save dataframes to CSV files
        students_df.to_csv(os.path.join(directory, 'Student_Info.csv'), index=False)
        teachers_df.to_csv(os.path.join(directory, 'Teacher_Info.csv'), index=False)
        sections_df.to_csv(os.path.join(directory, 'Sections_Information.csv'), index=False)
        periods_df.to_csv(os.path.join(directory, 'Period.csv'), index=False)
        preferences_df.to_csv(os.path.join(directory, 'Student_Preference_Info.csv'), index=False)
        unavailability_df.to_csv(os.path.join(directory, 'Teacher_unavailability.csv'), index=False)
    
    def test_scheduler_initialization(self, test_data_dir, output_dir):
        """Test that the scheduler can be initialized."""
        optimizer = ScheduleOptimizer(test_data_dir, output_dir)
        assert optimizer is not None
        assert optimizer.input_dir == Path(test_data_dir)
        assert optimizer.output_dir == Path(output_dir)
    
    def test_data_loading(self, test_data_dir, output_dir):
        """Test that data can be loaded."""
        optimizer = ScheduleOptimizer(test_data_dir, output_dir)
        data = optimizer.load_data()
        
        # Check that all expected dataframes are present
        assert 'students' in data
        assert 'teachers' in data
        assert 'sections' in data
        assert 'periods' in data
        assert 'student_preferences' in data
        assert 'teacher_unavailability' in data
        
        # Check that dataframes have expected number of rows
        assert len(data['students']) == 5
        assert len(data['teachers']) == 3
        assert len(data['sections']) == 5
        assert len(data['periods']) == 8
        assert len(data['student_preferences']) == 5
        assert len(data['teacher_unavailability']) == 3
    
    def test_data_conversion(self, test_data_dir, output_dir):
        """Test that data can be converted to domain objects."""
        optimizer = ScheduleOptimizer(test_data_dir, output_dir)
        data = optimizer.load_data()
        domain_data = optimizer.convert_data(data)
        
        # Check that all expected domain object collections are present
        assert 'students' in domain_data
        assert 'teachers' in domain_data
        assert 'sections' in domain_data
        assert 'periods' in domain_data
        assert 'student_preferences' in domain_data
        
        # Check that collections have expected number of items
        assert len(domain_data['students']) == 5
        assert len(domain_data['teachers']) == 3
        assert len(domain_data['sections']) == 5
        assert len(domain_data['periods']) == 8
        assert len(domain_data['student_preferences']) == 5
        
        # Check that objects have expected properties
        assert all(isinstance(s, Student) for s in domain_data['students'].values())
        assert all(isinstance(t, Teacher) for t in domain_data['teachers'].values())
        assert all(isinstance(s, Section) for s in domain_data['sections'].values())
        assert all(isinstance(p, Period) for p in domain_data['periods'].values())
        assert all(isinstance(p, StudentPreference) for p in domain_data['student_preferences'].values())
    
    def test_optimization(self, test_data_dir, output_dir):
        """Test the optimization process."""
        optimizer = ScheduleOptimizer(test_data_dir, output_dir)
        results = optimizer.optimize()
        
        # Check that results contain expected keys
        assert 'success' in results
        assert results['success'] is True
        assert 'schedule_summary' in results
        assert 'output_files' in results
        assert 'metrics' in results
        
        # Check schedule summary
        summary = results['schedule_summary']
        assert summary['total_sections'] == 5
        
        # Check that output files exist
        for file_path in results['output_files'].values():
            assert os.path.exists(file_path)
        
        # Check metrics
        assert results['metrics']['total_time'] > 0


class TestGreedyOptimizer:
    """Test the GreedyOptimizer class."""
    
    def test_greedy_optimization(self):
        """Test the greedy optimization algorithm."""
        # Create test data
        students = {
            'S001': Student(id='S001', first_name='John', last_name='Doe', 
                         email='jdoe@school.edu', grade_level=9),
            'S002': Student(id='S002', first_name='Jane', last_name='Smith', 
                         email='jsmith@school.edu', grade_level=10, has_special_needs=True)
        }
        
        teachers = {
            'T001': Teacher(id='T001', first_name='David', last_name='Jones', 
                         email='djones@school.edu', department='Math'),
            'T002': Teacher(id='T002', first_name='Sarah', last_name='Davis', 
                         email='sdavis@school.edu', department='Science')
        }
        
        sections = {
            'SEC001': Section(id='SEC001', course_id='MATH101', teacher_id='T001', capacity=30),
            'SEC002': Section(id='SEC002', course_id='SCI101', teacher_id='T002', capacity=25)
        }
        
        periods = {
            'P1': Period(id='P1', name='Period 1', start_time=pd.Timestamp('08:00').time(), 
                      end_time=pd.Timestamp('09:00').time(), day_of_week=0),
            'P2': Period(id='P2', name='Period 2', start_time=pd.Timestamp('09:00').time(), 
                      end_time=pd.Timestamp('10:00').time(), day_of_week=0)
        }
        
        student_preferences = {
            'S001': StudentPreference(student_id='S001', preferred_courses=['MATH101', 'SCI101']),
            'S002': StudentPreference(student_id='S002', preferred_courses=['SCI101'])
        }
        
        # Create optimizer and run optimization
        optimizer = GreedyOptimizer(
            students=students,
            teachers=teachers,
            sections=sections,
            periods=periods,
            student_preferences=student_preferences
        )
        
        schedule = optimizer.optimize()
        
        # Check that schedule is not None
        assert schedule is not None
        assert isinstance(schedule, Schedule)
        
        # Check that sections are in the schedule
        assert len(schedule.sections) == 2
        assert 'SEC001' in schedule.sections
        assert 'SEC002' in schedule.sections
        
        # Check that sections have been assigned periods
        assert all(section.period_id is not None for section in schedule.sections.values())
        
        # Check that there are some student assignments
        assert len(schedule.assignments) > 0