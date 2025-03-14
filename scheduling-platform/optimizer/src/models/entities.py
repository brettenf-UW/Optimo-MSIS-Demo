"""
Entity models for the schedule optimization system.
These classes represent the core domain objects used in the scheduling process.
"""
from dataclasses import dataclass, field
from typing import List, Dict, Optional, Set
from datetime import time


@dataclass
class Period:
    """Represents a time period in the school schedule."""
    id: str
    name: str
    start_time: time
    end_time: time
    day_of_week: int  # 0 = Monday, 6 = Sunday
    
    def __str__(self) -> str:
        days = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
        day_name = days[self.day_of_week]
        return f"{self.name}: {day_name} {self.start_time.strftime('%H:%M')} - {self.end_time.strftime('%H:%M')}"


@dataclass
class Teacher:
    """Represents a teacher with their teaching qualifications and constraints."""
    id: str
    first_name: str
    last_name: str
    email: str
    department: str
    max_sections: int = 5
    unavailable_periods: Set[str] = field(default_factory=set)
    
    @property
    def full_name(self) -> str:
        return f"{self.first_name} {self.last_name}"
    
    def is_available(self, period_id: str) -> bool:
        """Check if teacher is available for a given period."""
        return period_id not in self.unavailable_periods


@dataclass
class Student:
    """Represents a student with their academic information."""
    id: str
    first_name: str
    last_name: str
    email: str
    grade_level: int
    has_special_needs: bool = False
    
    @property
    def full_name(self) -> str:
        return f"{self.first_name} {self.last_name}"


@dataclass
class Course:
    """Represents a course offered in the curriculum."""
    id: str
    name: str
    department: str
    credits: int = 1
    description: str = ""


@dataclass
class Section:
    """Represents a specific offering of a course."""
    id: str
    course_id: str
    teacher_id: Optional[str] = None
    period_id: Optional[str] = None
    capacity: int = 30
    room: Optional[str] = None
    
    @property
    def is_scheduled(self) -> bool:
        """Check if section has been assigned a period."""
        return self.period_id is not None
    
    @property
    def has_teacher(self) -> bool:
        """Check if section has been assigned a teacher."""
        return self.teacher_id is not None and self.teacher_id != "Unassigned"


@dataclass
class StudentPreference:
    """Represents a student's course preferences."""
    student_id: str
    preferred_courses: List[str]
    required_courses: List[str] = field(default_factory=list)
    
    def is_required(self, course_id: str) -> bool:
        """Check if a course is required for this student."""
        return course_id in self.required_courses


@dataclass
class Assignment:
    """Represents an assignment of a student to a section."""
    student_id: str
    section_id: str
    
    def __eq__(self, other):
        if not isinstance(other, Assignment):
            return False
        return self.student_id == other.student_id and self.section_id == other.section_id
    
    def __hash__(self):
        return hash((self.student_id, self.section_id))


@dataclass
class Schedule:
    """Represents a complete schedule solution."""
    sections: Dict[str, Section]
    assignments: Set[Assignment] = field(default_factory=set)
    
    def assign_student(self, student_id: str, section_id: str) -> None:
        """Assign a student to a section."""
        self.assignments.add(Assignment(student_id, section_id))
    
    def get_student_assignments(self, student_id: str) -> List[str]:
        """Get all sections assigned to a student."""
        return [a.section_id for a in self.assignments if a.student_id == student_id]
    
    def get_section_enrollments(self, section_id: str) -> List[str]:
        """Get all students assigned to a section."""
        return [a.student_id for a in self.assignments if a.section_id == section_id]
    
    def get_enrollment_count(self, section_id: str) -> int:
        """Get the number of students enrolled in a section."""
        return len(self.get_section_enrollments(section_id))
    
    def is_section_full(self, section_id: str) -> bool:
        """Check if a section is at full capacity."""
        if section_id not in self.sections:
            return True
        return self.get_enrollment_count(section_id) >= self.sections[section_id].capacity