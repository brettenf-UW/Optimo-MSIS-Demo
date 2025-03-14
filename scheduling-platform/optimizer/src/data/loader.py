import pandas as pd
from pathlib import Path
import os
import datetime
import logging
from typing import Dict, Optional

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class ScheduleDataLoader:
    """
    Handles loading and validating scheduling data from CSV files.
    Provides validation and relationship checking between different data entities.
    """

    def __init__(self, input_dir: Optional[str] = None, debug_dir: Optional[str] = None):
        """
        Initialize the data loader with directories for input and debug files.
        
        Args:
            input_dir: Directory containing input CSV files
            debug_dir: Directory to store debug and log files
        """
        # Determine file paths
        self.project_root = Path(input_dir) if input_dir else Path.cwd()
        self.input_dir = self.project_root
        
        if debug_dir:
            self.debug_dir = Path(debug_dir)
        else:
            self.debug_dir = self.project_root / 'debug'
            
        self.debug_dir.mkdir(parents=True, exist_ok=True)

        # Create timestamped debug files
        timestamp = datetime.datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        self.log_file = self.debug_dir / f"data_loader_{timestamp}.log"
        
        # Setup file handler for logging
        file_handler = logging.FileHandler(self.log_file)
        file_handler.setFormatter(logging.Formatter('%(asctime)s - %(levelname)s - %(message)s'))
        logger.addHandler(file_handler)

        # Initialize data dictionary
        self.data = {}
        
        if not self.input_dir.exists():
            logger.error(f"Input directory not found at {self.input_dir}")
            raise FileNotFoundError(f"Input directory not found at {self.input_dir}")

        logger.info("Data loader initialized successfully")

    def load_base_data(self):
        """
        Load the primary data files required for scheduling:
        - Students
        - Teachers
        - Sections
        - Periods
        """
        try:
            logger.info("Loading base data files...")
            
            # Load students
            self.data['students'] = pd.read_csv(self.input_dir / 'Student_Info.csv')
            logger.info(f"Students loaded: {len(self.data['students'])} records")
            
            # Load teachers
            self.data['teachers'] = pd.read_csv(self.input_dir / 'Teacher_Info.csv')
            logger.info(f"Teachers loaded: {len(self.data['teachers'])} records")
            
            # Load sections
            self.data['sections'] = pd.read_csv(self.input_dir / 'Sections_Information.csv')
            logger.info(f"Sections loaded: {len(self.data['sections'])} records")
            
            # Load periods
            self.data['periods'] = pd.read_csv(self.input_dir / 'Period.csv')
            logger.info(f"Periods loaded: {len(self.data['periods'])} records")

        except FileNotFoundError as e:
            logger.error(f"Missing input file: {e.filename}")
            raise

    def load_relationship_data(self):
        """
        Load relationship data between primary entities:
        - Student preferences (requested courses)
        - Teacher unavailability (periods teachers can't teach)
        """
        try:
            logger.info("Loading relationship data...")
            
            # Load student preferences
            self.data['student_preferences'] = pd.read_csv(self.input_dir / 'Student_Preference_Info.csv')
            logger.info(f"Student preferences: {len(self.data['student_preferences'])} records")
            
            # Load teacher unavailability (handle case when file is missing)
            try:
                self.data['teacher_unavailability'] = pd.read_csv(self.input_dir / 'Teacher_unavailability.csv')
                logger.info(f"Teacher unavailability: {len(self.data['teacher_unavailability'])} records")
            except (pd.errors.EmptyDataError, FileNotFoundError):
                # Create empty DataFrame if file doesn't exist or is empty
                self.data['teacher_unavailability'] = pd.DataFrame(columns=['Teacher ID', 'Unavailable Periods'])
                logger.warning("Teacher unavailability not found or empty, using empty dataset")

        except FileNotFoundError as e:
            logger.error(f"Missing relationship file: {e.filename}")
            raise

    def validate_relationships(self):
        """
        Validate relationships and data consistency across loaded datasets.
        Checks for:
        - Teachers referenced in sections exist in teacher data
        - Courses requested by students exist in section data
        """
        logger.info("Validating data relationships...")
        validation_issues = []

        sections = self.data['sections']
        teachers = self.data['teachers']
        student_prefs = self.data['student_preferences']

        # Validate teachers
        teachers_in_sections = sections['Teacher Assigned'].unique()
        known_teachers = teachers['Teacher ID'].unique()
        unknown_teachers = set(teachers_in_sections) - set(known_teachers)
        
        if unknown_teachers:
            issue = f"Unknown teachers in sections: {unknown_teachers}"
            validation_issues.append(issue)
            logger.warning(issue)

        # Validate student preferences
        all_courses = sections['Course ID'].unique()
        MAX_LOG_ENTRIES = 100  # Limit logs for large datasets
        
        for idx, row in student_prefs.head(MAX_LOG_ENTRIES).iterrows():
            requested_courses = str(row['Preferred Sections']).split(';')
            unknown_courses = set(requested_courses) - set(all_courses)
            
            if unknown_courses:
                issue = f"Student {row['Student ID']} references unknown courses: {unknown_courses}"
                validation_issues.append(issue)
                logger.warning(issue)

        if not validation_issues:
            logger.info("All relationships are valid")
        else:
            logger.warning(f"Found {len(validation_issues)} validation issues")

        return validation_issues

    def load_all(self) -> Dict[str, pd.DataFrame]:
        """
        Load and validate all data required for scheduling optimization.
        
        Returns:
            Dict: Dictionary containing all loaded dataframes
        """
        try:
            logger.info("Starting data load process...")
            self.load_base_data()
            self.load_relationship_data()
            issues = self.validate_relationships()
            
            if issues:
                logger.warning(f"Data loaded with {len(issues)} validation issues")
            else:
                logger.info("Data loaded and validated successfully")
                
            return self.data
            
        except Exception as e:
            logger.error(f"Error during data loading: {str(e)}")
            raise


if __name__ == "__main__":
    # Test the loader directly when run as script
    try:
        loader = ScheduleDataLoader()
        data = loader.load_all()
        print("\nData loaded successfully:")
        for key, df in data.items():
            print(f" - {key}: {len(df)} records")
    except Exception as e:
        print(f"\nError: {str(e)}")