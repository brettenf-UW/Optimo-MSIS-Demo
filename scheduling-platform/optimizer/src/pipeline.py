"""
Integrated Optimization Pipeline

This module orchestrates the complete optimization process:
1. Greedy algorithm generates a warm start solution
2. MILP uses the warm start for further optimization
3. Schedule optimizer with Claude agent adjusts underutilized sections
4. Process repeats until all sections have at least 75% utilization

Usage:
python -m src.pipeline --input_dir /path/to/inputs --output_dir /path/to/outputs
"""
import os
import sys
import time
import json
import argparse
import logging
import pandas as pd
import requests
import gurobipy as gp
from pathlib import Path
from typing import Dict, List, Any, Tuple, Optional

# Local imports
from .optimizer import ScheduleOptimizer
from .algorithms.greedy import GreedyOptimizer
from .algorithms.milp import MILPOptimizer
from .models.entities import Schedule, Section
from .data.converter import DataConverter

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Claude API key
CLAUDE_API_KEY = "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"
CLAUDE_API_URL = "https://api.anthropic.com/v1/messages"

class OptimizationPipeline:
    """
    Pipeline that orchestrates the complete optimization process through multiple stages:
    1. Greedy optimization for warm start
    2. MILP optimization for optimal solution
    3. Section adjustment via Claude agent for underutilized sections
    4. Iterative refinement until utilization thresholds are met
    """
    
    def __init__(self, input_dir: str, output_dir: str, utilization_threshold: float = 0.75):
        """
        Initialize the optimization pipeline.
        
        Args:
            input_dir: Directory containing input files
            output_dir: Directory for output files
            utilization_threshold: Minimum section utilization threshold (default: 0.75)
        """
        self.input_dir = Path(input_dir)
        self.output_dir = Path(output_dir)
        self.utilization_threshold = utilization_threshold
        self.iteration = 0
        self.max_iterations = 5
        
        # Create iteration directories
        self.iterations_dir = self.output_dir / "iterations"
        self.iterations_dir.mkdir(parents=True, exist_ok=True)
        
        # Metrics for tracking performance
        self.metrics = {
            'total_time': 0,
            'greedy_time': 0,
            'milp_time': 0,
            'agent_time': 0,
            'initial_utilization': 0,
            'final_utilization': 0,
            'iterations': 0,
            'sections_adjusted': 0
        }
        
        logger.info(f"Initialized optimization pipeline with utilization threshold: {utilization_threshold}")
    
    def run(self) -> Dict[str, Any]:
        """
        Run the complete optimization pipeline.
        
        Returns:
            Dictionary with optimization results and metrics
        """
        start_time = time.time()
        logger.info("Starting optimization pipeline")
        
        # Initial input files are in the input directory
        current_input_dir = self.input_dir
        
        # Continue optimizing until we reach the target utilization or max iterations
        self.iteration = 0
        overall_result = None
        
        while self.iteration < self.max_iterations:
            logger.info(f"Starting iteration {self.iteration + 1}/{self.max_iterations}")
            
            # Create iteration output directory
            iteration_dir = self.iterations_dir / f"iteration_{self.iteration + 1}"
            iteration_dir.mkdir(exist_ok=True)
            
            try:
                # Run greedy optimization
                greedy_start = time.time()
                greedy_schedule, greedy_optimizer = self._run_greedy_optimization(current_input_dir, iteration_dir)
                self.metrics['greedy_time'] += time.time() - greedy_start
                
                # Run MILP optimization using greedy as warm start
                milp_start = time.time()
                milp_schedule = self._run_milp_optimization(
                    greedy_optimizer.students,
                    greedy_optimizer.teachers,
                    greedy_optimizer.sections,
                    greedy_optimizer.periods,
                    greedy_optimizer.student_preferences,
                    greedy_schedule,
                    iteration_dir
                )
                self.metrics['milp_time'] += time.time() - milp_start
                
                # Check utilization and identify underutilized sections
                utilization_df = DataConverter.generate_utilization_report(milp_schedule)
                underutilized_sections = utilization_df[
                    utilization_df['Utilization'] < self.utilization_threshold
                ]
                
                # Log details about underutilized sections
                logger.info(f"Found {len(underutilized_sections)} sections below {self.utilization_threshold*100}% utilization:")
                for _, row in underutilized_sections.iterrows():
                    logger.info(f"  - Section {row['Section ID']} ({row['Course ID']}): {row['Utilization']:.2%} utilization ({row['Enrollment']}/{row['Capacity']} students)")
                
                # Record metrics for this iteration
                avg_utilization = utilization_df['Utilization'].mean()
                if self.iteration == 0:
                    self.metrics['initial_utilization'] = avg_utilization
                
                logger.info(f"Iteration {self.iteration + 1} - Average utilization: {avg_utilization:.2f}")
                logger.info(f"Found {len(underutilized_sections)} underutilized sections")
                
                # If no underutilized sections or reached max iterations, we're done
                if len(underutilized_sections) == 0 or self.iteration == self.max_iterations - 1:
                    overall_result = {
                        'schedule': milp_schedule,
                        'utilization': utilization_df,
                        'output_dir': str(iteration_dir)
                    }
                    self.metrics['final_utilization'] = avg_utilization
                    break
                
                # If this is the first iteration and there are a lot of underutilized sections,
                # we might want to skip running Claude agent and just use the first iteration result
                if self.iteration == 0 and len(underutilized_sections) > 10:
                    logger.warning(f"Found {len(underutilized_sections)} underutilized sections in first iteration")
                    logger.warning("This suggests fundamental data issues that section adjustments may not fix")
                    logger.info("Continuing with section adjustments, but consider reviewing input data")
                
                # Run Claude agent to adjust underutilized sections - safer version that won't create problematic sections
                agent_start = time.time()
                new_input_files = self._run_claude_agent(
                    milp_schedule, 
                    underutilized_sections, 
                    current_input_dir,
                    iteration_dir
                )
                self.metrics['agent_time'] += time.time() - agent_start
                
                # Check if any actions were actually performed
                actions_performed = self._check_if_changes_made(current_input_dir, new_input_files)
                if not actions_performed:
                    logger.info("No changes were made by the Claude agent - using current result as final")
                    overall_result = {
                        'schedule': milp_schedule,
                        'utilization': utilization_df,
                        'output_dir': str(iteration_dir)
                    }
                    self.metrics['final_utilization'] = avg_utilization
                    break
                
                # Update metrics
                self.metrics['sections_adjusted'] += len(underutilized_sections)
                
                # Use the new input files for the next iteration
                current_input_dir = new_input_files
                
            except Exception as e:
                logger.error(f"Error in iteration {self.iteration + 1}: {str(e)}")
                logger.info("Using results from last successful iteration")
                
                if self.iteration == 0:
                    # If we fail on the first iteration, we don't have any results yet
                    raise RuntimeError(f"Failed on first iteration: {str(e)}")
                else:
                    # Use the results from the previous iteration
                    break
            
            # Increment iteration counter
            self.iteration += 1
            self.metrics['iterations'] = self.iteration + 1
            
    def _check_if_changes_made(self, original_dir: Path, new_dir: Path) -> bool:
        """
        Check if any changes were made between the original and new input files.
        
        Args:
            original_dir: Path to original input directory
            new_dir: Path to new input directory
            
        Returns:
            True if changes were made, False otherwise
        """
        original_sections = pd.read_csv(original_dir / "Sections_Information.csv")
        new_sections = pd.read_csv(new_dir / "Sections_Information.csv")
        
        # Simple check - did the number of sections change?
        if len(original_sections) != len(new_sections):
            return True
            
        # Check if the section IDs changed
        original_ids = set(original_sections["Section ID"])
        new_ids = set(new_sections["Section ID"])
        
        if original_ids != new_ids:
            return True
            
        # No significant changes detected
        logger.info("No significant changes detected between iterations")
        return False
    
    def run(self) -> Dict[str, Any]:
        """
        Run the complete optimization pipeline.
        
        Returns:
            Dictionary with optimization results and metrics
        """
        start_time = time.time()
        logger.info("Starting optimization pipeline")
        
        # Initial input files are in the input directory
        current_input_dir = self.input_dir
        
        # Continue optimizing until we reach the target utilization or max iterations
        self.iteration = 0
        overall_result = None
        
        # Main optimization loop
        while self.iteration < self.max_iterations:
            logger.info(f"Starting iteration {self.iteration + 1}/{self.max_iterations}")
            
            # Create iteration output directory
            iteration_dir = self.iterations_dir / f"iteration_{self.iteration + 1}"
            iteration_dir.mkdir(exist_ok=True)
            
            try:
                # Run greedy optimization
                greedy_start = time.time()
                greedy_schedule, greedy_optimizer = self._run_greedy_optimization(current_input_dir, iteration_dir)
                self.metrics['greedy_time'] += time.time() - greedy_start
                
                # Run MILP optimization using greedy as warm start
                milp_start = time.time()
                milp_schedule = self._run_milp_optimization(
                    greedy_optimizer.students,
                    greedy_optimizer.teachers,
                    greedy_optimizer.sections,
                    greedy_optimizer.periods,
                    greedy_optimizer.student_preferences,
                    greedy_schedule,
                    iteration_dir
                )
                self.metrics['milp_time'] += time.time() - milp_start
                
                # Store the last successful iteration data
                last_success = {
                    'schedule': milp_schedule,
                    'utilization': DataConverter.generate_utilization_report(milp_schedule),
                    'output_dir': str(iteration_dir)
                }
                
                # Check utilization and identify underutilized sections
                utilization_df = last_success['utilization']
                underutilized_sections = utilization_df[
                    utilization_df['Utilization'] < self.utilization_threshold
                ]
                
                # Log details about underutilized sections
                logger.info(f"Found {len(underutilized_sections)} sections below {self.utilization_threshold*100}% utilization:")
                for _, row in underutilized_sections.iterrows():
                    logger.info(f"  - Section {row['Section ID']} ({row['Course ID']}): {row['Utilization']:.2%} utilization ({row['Enrollment']}/{row['Capacity']} students)")
                
                # Record metrics for this iteration
                avg_utilization = utilization_df['Utilization'].mean()
                if self.iteration == 0:
                    self.metrics['initial_utilization'] = avg_utilization
                
                logger.info(f"Iteration {self.iteration + 1} - Average utilization: {avg_utilization:.2f}")
                logger.info(f"Found {len(underutilized_sections)} underutilized sections")
                
                # If no underutilized sections or reached max iterations, we're done
                if len(underutilized_sections) == 0 or self.iteration == self.max_iterations - 1:
                    overall_result = last_success
                    self.metrics['final_utilization'] = avg_utilization
                    break
                
                # Run Claude agent to adjust underutilized sections
                agent_start = time.time()
                new_input_files = self._run_claude_agent(
                    milp_schedule, 
                    underutilized_sections, 
                    current_input_dir,
                    iteration_dir
                )
                self.metrics['agent_time'] += time.time() - agent_start
                
                # Check if any actions were actually performed
                actions_performed = self._check_if_changes_made(current_input_dir, new_input_files)
                if not actions_performed:
                    logger.info("No changes were made by the Claude agent - using current result as final")
                    overall_result = last_success
                    self.metrics['final_utilization'] = avg_utilization
                    break
                
                # Update metrics
                self.metrics['sections_adjusted'] += len(underutilized_sections)
                
                # Use the new input files for the next iteration
                current_input_dir = new_input_files
                
            except Exception as e:
                logger.error(f"Error in iteration {self.iteration + 1}: {str(e)}")
                logger.info("Using results from last successful iteration")
                
                if self.iteration == 0:
                    # If we fail on the first iteration, we don't have any results yet
                    raise RuntimeError(f"Failed on first iteration: {str(e)}")
                else:
                    # Use the results from the previous iteration
                    overall_result = last_success
                    break
            
            # Increment iteration counter
            self.iteration += 1
            self.metrics['iterations'] = self.iteration + 1
        
        # Save final outputs
        final_output_dir = self.output_dir / "final"
        final_output_dir.mkdir(exist_ok=True)
        
        # Copy final files if we have them
        if overall_result:
            self._save_final_results(overall_result['schedule'], overall_result['utilization'], final_output_dir)
        
        # Calculate total time
        self.metrics['total_time'] = time.time() - start_time
        
        # Create final results
        results = {
            'success': True,
            'output_dir': str(final_output_dir),
            'metrics': self.metrics,
            'iterations': self.iteration + 1
        }
        
        logger.info(f"Optimization pipeline completed in {self.metrics['total_time']:.2f} seconds")
        logger.info(f"Initial utilization: {self.metrics['initial_utilization']:.2f}, "
                    f"Final utilization: {self.metrics['final_utilization']:.2f}")
        
        # Save metrics to file
        with open(self.output_dir / "metrics.json", "w") as f:
            json.dump(self.metrics, f, indent=2)
        
        return results
    
    def _run_greedy_optimization(self, input_dir: Path, output_dir: Path) -> Tuple[Schedule, GreedyOptimizer]:
        """
        Run the greedy optimization algorithm.
        
        Args:
            input_dir: Directory containing input files
            output_dir: Directory to save output files
            
        Returns:
            Tuple of (Schedule object, GreedyOptimizer instance)
        """
        logger.info(f"Running greedy optimization with input from {input_dir}")
        
        # Initialize optimizer with input files
        optimizer = ScheduleOptimizer(input_dir, output_dir)
        
        # Load and convert data
        data = optimizer.load_data()
        domain_data = optimizer.convert_data(data)
        
        # Create the greedy optimizer
        greedy_optimizer = GreedyOptimizer(
            students=domain_data['students'],
            teachers=domain_data['teachers'],
            sections=domain_data['sections'],
            periods=domain_data['periods'],
            student_preferences=domain_data['student_preferences']
        )
        
        # Run greedy optimization
        schedule = greedy_optimizer.optimize()
        
        # Save the warm start results
        optimizer.save_results(schedule)
        
        logger.info(f"Greedy optimization complete - scheduled {len([s for s in schedule.sections.values() if s.is_scheduled])}/{len(schedule.sections)} sections")
        
        return schedule, greedy_optimizer
    
    def _run_milp_optimization(self, 
                              students: Dict, 
                              teachers: Dict, 
                              sections: Dict, 
                              periods: Dict, 
                              student_preferences: Dict,
                              warm_start: Schedule,
                              output_dir: Path) -> Schedule:
        """
        Run the MILP optimization algorithm using the greedy solution as a warm start.
        
        Args:
            students: Dictionary of students
            teachers: Dictionary of teachers
            sections: Dictionary of sections
            periods: Dictionary of periods
            student_preferences: Dictionary of student preferences
            warm_start: Schedule from greedy optimization to use as warm start
            output_dir: Directory to save output files
            
        Returns:
            Optimized Schedule object
        """
        logger.info("Running MILP optimization with warm start from greedy algorithm")
        
        try:
            # Create the MILP optimizer with warm start from greedy
            milp_optimizer = MILPOptimizer(
                students=students,
                teachers=teachers,
                sections=sections,
                periods=periods,
                student_preferences=student_preferences,
                warm_start=warm_start,  # Use greedy solution as warm start
                time_limit_seconds=900  # 15 minutes max
            )
            
            # Run MILP optimization
            schedule = milp_optimizer.optimize()
            
            # Verify we got a valid solution (should have at least one scheduled section)
            scheduled_sections = [s for s in schedule.sections.values() if s.is_scheduled]
            if not scheduled_sections:
                logger.warning("MILP optimization returned no scheduled sections")
                logger.info("Falling back to greedy solution")
                schedule = warm_start
            else:
                logger.info(f"MILP optimization successfully scheduled {len(scheduled_sections)} sections")
                
        except gp.GurobiError as e:
            logger.warning(f"MILP optimization failed with Gurobi error: {str(e)}")
            logger.info("Falling back to greedy solution")
            schedule = warm_start
        except Exception as e:
            logger.warning(f"MILP optimization failed with unexpected error: {str(e)}")
            import traceback
            logger.debug(f"Stack trace: {traceback.format_exc()}")
            logger.info("Falling back to greedy solution")
            schedule = warm_start
        
        # Save results (either from MILP or greedy if MILP failed)
        converter = DataConverter()
        
        # Convert schedule to DataFrames
        master_schedule_df = converter.convert_to_master_schedule_df(schedule)
        student_assignments_df = converter.convert_to_student_assignments_df(schedule)
        teacher_schedule_df = converter.convert_to_teacher_schedule_df(schedule)
        utilization_report_df = converter.generate_utilization_report(schedule)
        
        # Define output file paths
        output_files = {
            'master_schedule': str(output_dir / 'Master_Schedule.csv'),
            'student_assignments': str(output_dir / 'Student_Assignments.csv'),
            'teacher_schedule': str(output_dir / 'Teacher_Schedule.csv'),
            'utilization_report': str(output_dir / 'Utilization_Report.csv')
        }
        
        # Save DataFrames to CSV files
        master_schedule_df.to_csv(output_files['master_schedule'], index=False)
        student_assignments_df.to_csv(output_files['student_assignments'], index=False)
        teacher_schedule_df.to_csv(output_files['teacher_schedule'], index=False)
        utilization_report_df.to_csv(output_files['utilization_report'], index=False)
        
        logger.info(f"Optimization complete - scheduled {len([s for s in schedule.sections.values() if s.is_scheduled])}/{len(schedule.sections)} sections")
        
        return schedule
    
    def _run_claude_agent(self, 
                         schedule: Schedule, 
                         underutilized_sections: pd.DataFrame, 
                         input_dir: Path,
                         output_dir: Path) -> Path:
        """
        Run the Claude agent to optimize underutilized sections.
        
        Args:
            schedule: Current schedule
            underutilized_sections: DataFrame of sections below utilization threshold
            input_dir: Directory containing current input files
            output_dir: Directory to save output files
            
        Returns:
            Path to directory with new input files
        """
        logger.info(f"Running Claude agent for {len(underutilized_sections)} underutilized sections")
        
        # Create a prompt for Claude with the underutilized sections
        prompt = self._create_claude_prompt(schedule, underutilized_sections, input_dir)
        
        # Call Claude API
        response = self._call_claude_api(prompt)
        
        # Process Claude's response to generate new input files
        new_input_dir = output_dir / "new_inputs"
        new_input_dir.mkdir(exist_ok=True)
        
        # Parse Claude's response
        actions = self._parse_claude_response(response)
        
        # Apply the actions to generate new input files
        self._apply_schedule_actions(schedule, actions, input_dir, new_input_dir)
        
        logger.info(f"Claude agent complete - generated new input files in {new_input_dir}")
        
        return new_input_dir
    
    def _create_claude_prompt(self, schedule: Schedule, 
                            underutilized_sections: pd.DataFrame, 
                            input_dir: Path) -> str:
        """
        Create a prompt for Claude with the current schedule state and underutilized sections.
        
        Args:
            schedule: Current schedule
            underutilized_sections: DataFrame of sections below utilization threshold
            input_dir: Directory containing current input files
            
        Returns:
            Prompt string for Claude
        """
        # Read the current input files to include in the prompt
        sections_df = pd.read_csv(input_dir / "Sections_Information.csv")
        students_df = pd.read_csv(input_dir / "Student_Info.csv")
        preferences_df = pd.read_csv(input_dir / "Student_Preference_Info.csv")
        
        # Format the underutilized sections data
        underutilized_str = underutilized_sections.to_string(index=False)
        
        # Format the schedule summary
        schedule_summary = {
            'total_sections': len(schedule.sections),
            'scheduled_sections': len([s for s in schedule.sections.values() if s.is_scheduled]),
            'total_assignments': len(schedule.assignments),
            'total_students': len(set(a.student_id for a in schedule.assignments))
        }
        
        # Create the prompt
        prompt = f"""
        You are an AI registrar assistant helping optimize a school schedule. We have identified underutilized sections 
        (below {self.utilization_threshold*100}% capacity) that need adjustment. For each underutilized section, 
        recommend ONE of the following actions:
        
        1. SPLIT: Divide a section into two smaller sections
        2. ADD: Create a new section to meet demand
        3. REMOVE: Remove the section if there's not enough demand
        4. MERGE: Combine with another section (specify which one)
        
        Current Schedule Summary:
        - Total Sections: {schedule_summary['total_sections']}
        - Scheduled Sections: {schedule_summary['scheduled_sections']}
        - Total Student Assignments: {schedule_summary['total_assignments']}
        - Total Students: {schedule_summary['total_students']}
        
        Underutilized Sections:
        {underutilized_str}
        
        Please analyze each underutilized section and recommend what action to take.
        Format your response as a JSON list of actions. For example:
        
        [
          {{
            "section_id": "S001",
            "action": "MERGE",
            "merge_with": "S002",
            "reason": "Both sections have low enrollment and compatible schedules"
          }},
          {{
            "section_id": "S003",
            "action": "REMOVE",
            "reason": "Very low enrollment with alternative sections available"
          }}
        ]
        
        Provide detailed reasoning for each recommendation, considering student preferences, 
        teacher availability, and overall schedule optimization.
        """
        
        return prompt
    
    def _call_claude_api(self, prompt: str) -> str:
        """
        Call the Claude API with the given prompt.
        
        Args:
            prompt: The prompt to send to Claude
            
        Returns:
            Claude's response text
        """
        logger.info("Calling Claude API")
        
        # Try to make a real call to the Claude API
        try:
            # Configure API request
            headers = {
                "x-api-key": CLAUDE_API_KEY,
                "Content-Type": "application/json",
                "anthropic-version": "2023-06-01"
            }
            
            payload = {
                "model": "claude-3-sonnet-20240229",  # Use Sonnet for better cost efficiency
                "max_tokens": 2000,
                "messages": [
                    {"role": "user", "content": prompt}
                ]
            }
            
            # Make the API call
            try:
                import requests
                response = requests.post(CLAUDE_API_URL, json=payload, headers=headers)
                
                if response.status_code == 200:
                    response_data = response.json()
                    claude_response = response_data["content"][0]["text"]
                    logger.info("Successfully received response from Claude API")
                    return claude_response
                else:
                    logger.error(f"Claude API error: {response.status_code} - {response.text}")
            except Exception as e:
                logger.warning(f"Error making Claude API request: {str(e)}")
        except Exception as e:
            logger.warning(f"Error preparing Claude API call: {str(e)}")
        
        # If we get here, the API call failed - use fallback logic
        logger.info("Using fallback section adjustment logic")
        
        # Get the actual underutilized sections from the data
        underutilized_section_ids = underutilized_sections["Section ID"].tolist()
        if not underutilized_section_ids:
            logger.warning("No underutilized sections found to adjust")
            return "[]"  # Return empty JSON array if no sections to adjust
            
        # Create intelligent fallback logic based on actual underutilized sections
        actions = []
        
        # First, read in all the CSV data to make intelligent decisions
        try:
            sections_df = pd.read_csv(current_input_dir / "Sections_Information.csv")
            teachers_df = pd.read_csv(current_input_dir / "Teacher_Info.csv")
            
            # Count how many sections each teacher is assigned to
            teacher_section_counts = {}
            for _, row in sections_df.iterrows():
                teacher_id = row["Teacher Assigned"]
                teacher_section_counts[teacher_id] = teacher_section_counts.get(teacher_id, 0) + 1
                
            # Map teachers to the courses they teach
            teacher_courses = {}
            for _, row in sections_df.iterrows():
                teacher_id = row["Teacher Assigned"]
                course_id = row["Course ID"]
                if teacher_id not in teacher_courses:
                    teacher_courses[teacher_id] = set()
                teacher_courses[teacher_id].add(course_id)
                
            # Find sections that need merging (similar sections with low enrollment)
            mergeable_sections = {}
            for course_id in sections_df["Course ID"].unique():
                course_sections = sections_df[sections_df["Course ID"] == course_id]
                if len(course_sections) >= 2:  # Need at least 2 sections to merge
                    # Find underutilized sections of this course
                    course_low_util = [
                        section_id for section_id in underutilized_section_ids 
                        if section_id in course_sections["Section ID"].values
                    ]
                    if len(course_low_util) >= 2:
                        mergeable_sections[course_id] = course_low_util
                        
            # For each underutilized section, determine the best action
            for section_id in underutilized_section_ids[:3]:  # Limit to first 3 to avoid too many changes
                section_row = underutilized_sections[underutilized_sections["Section ID"] == section_id].iloc[0]
                section_data = sections_df[sections_df["Section ID"] == section_id].iloc[0]
                utilization = section_row["Utilization"]
                course_id = section_row["Course ID"]
                enrollment = section_row["Enrollment"]
                capacity = section_row["Capacity"]
                teacher_id = section_data["Teacher Assigned"]
                department = section_data["Department"]
                
                # Check if current size is outside the optimal range
                if capacity > 35:
                    # Section is too large, should be split
                    # Find another teacher who teaches this course or in this department
                    potential_teachers = []
                    for tid, courses in teacher_courses.items():
                        if tid != teacher_id and (
                            course_id in courses or  # Already teaches this course
                            (tid in teachers_df["Teacher ID"].values and  # In same department
                             teachers_df[teachers_df["Teacher ID"] == tid]["Department"].iloc[0] == department)
                        ):
                            # Check if this teacher has 5 or fewer sections
                            if teacher_section_counts.get(tid, 0) <= 5:
                                potential_teachers.append(tid)
                                
                    if potential_teachers:
                        # Split into two sections of reasonable size
                        actions.append({
                            "section_id": section_id,
                            "action": "SPLIT",
                            "reason": f"Section is too large ({capacity} seats). Splitting to optimize class size."
                        })
                        continue
                
                # Very low enrollment and utilization
                if enrollment < 15 and utilization < 0.4:
                    # Check if we can merge with another section
                    if course_id in mergeable_sections and len(mergeable_sections[course_id]) >= 2:
                        merge_candidates = [s for s in mergeable_sections[course_id] if s != section_id]
                        if merge_candidates:
                            merge_with = merge_candidates[0]
                            actions.append({
                                "section_id": section_id,
                                "action": "MERGE",
                                "merge_with": merge_with,
                                "reason": f"Both sections have low enrollment and can be combined to optimize resources."
                            })
                            # Remove the used section from candidates
                            mergeable_sections[course_id].remove(merge_with)
                            continue
                    
                    # If not mergeable and very low enrollment, remove it
                    # But protect special courses unless extremely low enrollment
                    if course_id not in ["Medical Career", "Heroes Teach"] or enrollment < 5:
                        actions.append({
                            "section_id": section_id,
                            "action": "REMOVE",
                            "reason": f"Section has very low enrollment ({enrollment}) and utilization ({utilization:.1%})."
                        })
                        continue
                
                # For sections with moderate demand but still under threshold
                if 0.5 <= utilization < 0.75 and enrollment >= 15:
                    # Check if there's high overall demand for this course
                    course_sections = sections_df[sections_df["Course ID"] == course_id]
                    course_section_ids = course_sections["Section ID"].tolist()
                    
                    # Check if other sections of this course are highly utilized
                    other_sections_highly_utilized = False
                    for other_id in course_section_ids:
                        if other_id != section_id and other_id in utilization_df["Section ID"].values:
                            other_util = utilization_df[utilization_df["Section ID"] == other_id]["Utilization"].iloc[0]
                            if other_util > 0.9:  # Other section is nearly full
                                other_sections_highly_utilized = True
                                break
                                
                    if other_sections_highly_utilized:
                        # Find a teacher who can teach another section
                        potential_teachers = []
                        for tid, courses in teacher_courses.items():
                            if course_id in courses and teacher_section_counts.get(tid, 0) <= 5:
                                potential_teachers.append(tid)
                                
                        if potential_teachers:
                            # Add a new section to meet demand
                            actions.append({
                                "section_id": section_id,
                                "action": "ADD",
                                "reason": f"High demand for {course_id} with other sections nearly full. Adding a new section."
                            })
                            continue
                            
                # If we get here, no specific action needed for this section
                logger.info(f"No specific action needed for section {section_id} with utilization {utilization:.1%}")
                
        except Exception as e:
            logger.error(f"Error analyzing sections for adjustment: {str(e)}")
            # Fallback to basic removal of very underutilized sections
            for section_id in underutilized_section_ids[:2]:
                section_row = underutilized_sections[underutilized_sections["Section ID"] == section_id].iloc[0]
                utilization = section_row["Utilization"]
                if utilization < 0.3:
                    actions.append({
                        "section_id": section_id,
                        "action": "REMOVE",
                        "reason": f"Section has very low utilization ({utilization:.1%})."
                    })
            
        # Convert actions to JSON string
        simulated_response = f"""
        I've analyzed the underutilized sections and here are my recommendations:
        
        {json.dumps(actions, indent=2)}
        """
        
        logger.info(f"Generated fallback response with {len(actions)} actions")
        
        return simulated_response
    
    def _parse_claude_response(self, response: str) -> List[Dict[str, Any]]:
        """
        Parse Claude's response to extract the recommended actions.
        
        Args:
            response: Claude's response text
            
        Returns:
            List of action dictionaries
        """
        logger.info("Parsing Claude response")
        
        # Find JSON block - in a real implementation, you'd use proper JSON extraction
        try:
            # Look for text between square brackets
            start_idx = response.find("[")
            end_idx = response.rfind("]") + 1
            
            if start_idx >= 0 and end_idx > start_idx:
                json_str = response[start_idx:end_idx]
                actions = json.loads(json_str)
                return actions
            else:
                logger.error("Could not find JSON block in Claude response")
                return []
        except json.JSONDecodeError:
            logger.error("Could not parse JSON from Claude response")
            return []
    
    def _apply_schedule_actions(self, 
                              schedule: Schedule, 
                              actions: List[Dict[str, Any]], 
                              input_dir: Path, 
                              output_dir: Path) -> None:
        """
        Apply the actions recommended by Claude to generate new input files.
        
        Args:
            schedule: Current schedule
            actions: List of actions from Claude
            input_dir: Directory containing current input files
            output_dir: Directory to save new input files
        """
        logger.info(f"Applying {len(actions)} schedule actions")
        
        # Read original input files
        sections_df = pd.read_csv(input_dir / "Sections_Information.csv")
        students_df = pd.read_csv(input_dir / "Student_Info.csv")
        preferences_df = pd.read_csv(input_dir / "Student_Preference_Info.csv")
        teachers_df = pd.read_csv(input_dir / "Teacher_Info.csv")
        periods_df = pd.read_csv(input_dir / "Period.csv")
        
        # Process each action
        for action in actions:
            section_id = action["section_id"]
            action_type = action["action"]
            
            if action_type == "MERGE":
                # Merge two sections
                merge_with = action["merge_with"]
                self._merge_sections(sections_df, preferences_df, section_id, merge_with)
            elif action_type == "REMOVE":
                # Remove a section
                self._remove_section(sections_df, preferences_df, section_id)
            elif action_type == "SPLIT":
                # Split a section into two
                self._split_section(sections_df, teachers_df, section_id)
            elif action_type == "ADD":
                # Add a new section
                self._add_section(sections_df, teachers_df, section_id)
        
        # Save the modified input files
        sections_df.to_csv(output_dir / "Sections_Information.csv", index=False)
        students_df.to_csv(output_dir / "Student_Info.csv", index=False)
        preferences_df.to_csv(output_dir / "Student_Preference_Info.csv", index=False)
        teachers_df.to_csv(output_dir / "Teacher_Info.csv", index=False)
        periods_df.to_csv(output_dir / "Period.csv", index=False)
        
        # Copy any other files from input_dir to output_dir
        for file_path in input_dir.glob("*.csv"):
            if file_path.name not in ["Sections_Information.csv", "Student_Info.csv", 
                                     "Student_Preference_Info.csv", "Teacher_Info.csv", 
                                     "Period.csv"]:
                output_file = output_dir / file_path.name
                if not output_file.exists():
                    with open(file_path, "rb") as src, open(output_file, "wb") as dst:
                        dst.write(src.read())
    
    def _merge_sections(self, sections_df: pd.DataFrame, preferences_df: pd.DataFrame, 
                      section_id1: str, section_id2: str) -> None:
        """Merge two sections into one"""
        # Check if both sections exist
        if not any(sections_df["Section ID"] == section_id1):
            logger.warning(f"Section {section_id1} not found in sections DataFrame")
            return
        
        if not any(sections_df["Section ID"] == section_id2):
            logger.warning(f"Section {section_id2} not found in sections DataFrame")
            return
            
        # Get section information
        section1 = sections_df[sections_df["Section ID"] == section_id1].iloc[0]
        section2 = sections_df[sections_df["Section ID"] == section_id2].iloc[0]
        
        # Verify they are the same course
        if section1["Course ID"] != section2["Course ID"]:
            logger.warning(f"Cannot merge sections with different courses: {section_id1}, {section_id2}")
            return
            
        # Calculate total enrollment (assuming we're merging because both are under-enrolled)
        # Ensure the merged section isn't too large (max 35 students)
        total_capacity = section1["# of Seats Available"] + section2["# of Seats Available"]
        if total_capacity > 35:
            # Cap at 35
            logger.info(f"Capping merged section capacity at 35 (from original {total_capacity})")
            total_capacity = 35
        
        # Update section capacity
        sections_df.loc[sections_df["Section ID"] == section_id1, "# of Seats Available"] = total_capacity
        
        # Remove the second section
        sections_df.drop(sections_df[sections_df["Section ID"] == section_id2].index, inplace=True)
        
        # Update student preferences
        for idx, row in preferences_df.iterrows():
            if pd.notna(row["Preferred Sections"]):
                sections = row["Preferred Sections"].split(";")
                if section_id2 in sections:
                    sections.remove(section_id2)
                    if section_id1 not in sections:
                        sections.append(section_id1)
                    preferences_df.loc[idx, "Preferred Sections"] = ";".join(sections)
                    
        logger.info(f"Merged sections {section_id1} and {section_id2} with new capacity {total_capacity}")
    
    def _remove_section(self, sections_df: pd.DataFrame, preferences_df: pd.DataFrame, 
                       section_id: str) -> None:
        """Remove a section"""
        # Check if section exists
        if not any(sections_df["Section ID"] == section_id):
            logger.warning(f"Section {section_id} not found in sections DataFrame")
            return
            
        # Get section information before removing
        section = sections_df[sections_df["Section ID"] == section_id].iloc[0]
        course_id = section["Course ID"]
        teacher_id = section["Teacher Assigned"]
        
        # Count how many sections this teacher has
        teacher_section_count = len(sections_df[sections_df["Teacher Assigned"] == teacher_id])
        
        # Don't remove if this is the teacher's only section
        if teacher_section_count <= 1:
            logger.warning(f"Cannot remove section {section_id} - it's the only section for teacher {teacher_id}")
            return
            
        # Also count how many sections exist for this course
        course_section_count = len(sections_df[sections_df["Course ID"] == course_id])
        
        # Don't remove if this is the only section for this course
        if course_section_count <= 1:
            logger.warning(f"Cannot remove section {section_id} - it's the only section for course {course_id}")
            return
        
        # Remove the section
        sections_df.drop(sections_df[sections_df["Section ID"] == section_id].index, inplace=True)
        
        # Update student preferences
        for idx, row in preferences_df.iterrows():
            if pd.notna(row["Preferred Sections"]):
                sections = row["Preferred Sections"].split(";")
                if section_id in sections:
                    sections.remove(section_id)
                    preferences_df.loc[idx, "Preferred Sections"] = ";".join(sections)
                    
        logger.info(f"Removed section {section_id} for course {course_id}")
    
    def _split_section(self, sections_df: pd.DataFrame, teachers_df: pd.DataFrame, 
                      section_id: str) -> None:
        """Split a section into two"""
        # Check if section exists
        if not any(sections_df["Section ID"] == section_id):
            logger.warning(f"Section {section_id} not found in sections DataFrame")
            return
            
        # Get section information
        section = sections_df[sections_df["Section ID"] == section_id].iloc[0]
        original_capacity = section["# of Seats Available"]
        
        # Verify the section is actually large enough to split
        if original_capacity <= 30:
            logger.warning(f"Section {section_id} capacity ({original_capacity}) is not large enough to split")
            return
            
        # Determine capacities for the two sections
        # If original capacity is odd, give the extra seat to the original section
        new_capacity1 = original_capacity // 2 + (original_capacity % 2)  
        new_capacity2 = original_capacity // 2
        
        # Ensure both sections have at least 15 seats
        if new_capacity1 < 15 or new_capacity2 < 15:
            logger.warning(f"Cannot split section {section_id} - resulting sections would be too small")
            return
            
        # Create a new section ID based on sequential numbering
        # Extract all section numbers
        section_numbers = []
        for s in sections_df["Section ID"]:
            if s.startswith("S"):
                # Remove the 'S' prefix and take only digits before any underscore
                base = s[1:].split('_')[0]
                try:
                    section_numbers.append(int(base))
                except ValueError:
                    # Skip if we can't convert to integer
                    pass
                
        # Generate new section ID
        new_section_num = max(section_numbers) + 1 if section_numbers else 1
        new_section_id = f"S{new_section_num:03d}"
        
        # Count sections per teacher
        teacher_counts = sections_df.groupby("Teacher Assigned").size().to_dict()
        
        # Find a teacher who:
        # 1. Is qualified to teach this course (already teaches it)
        # 2. Has fewer than 6 classes
        # 3. Is in the same department
        
        current_teacher = section["Teacher Assigned"]
        course_id = section["Course ID"]
        department = section["Department"]
        
        # Find teachers who teach this course
        qualified_teachers = sections_df[sections_df["Course ID"] == course_id]["Teacher Assigned"].unique()
        
        # Find teachers in the same department
        dept_teachers = teachers_df[teachers_df["Department"] == department]["Teacher ID"].unique()
        
        # Prioritize teachers already teaching this course
        potential_teachers = []
        for teacher in qualified_teachers:
            if teacher != current_teacher and teacher_counts.get(teacher, 0) < 6:
                potential_teachers.append(teacher)
                
        # If no qualified teachers, look at department teachers
        if not potential_teachers:
            for teacher in dept_teachers:
                if teacher != current_teacher and teacher_counts.get(teacher, 0) < 6:
                    potential_teachers.append(teacher)
        
        # If still no teachers, use current teacher (if they have fewer than 6 classes)
        if not potential_teachers and teacher_counts.get(current_teacher, 0) < 6:
            new_teacher = current_teacher
        elif potential_teachers:
            new_teacher = potential_teachers[0]
        else:
            logger.warning(f"Cannot find teacher for new section when splitting {section_id}")
            return
        
        # Update original section capacity
        sections_df.loc[sections_df["Section ID"] == section_id, "# of Seats Available"] = new_capacity1
        
        # Create new section with copied data but new capacity
        new_row = section.copy()
        new_row["Section ID"] = new_section_id
        new_row["# of Seats Available"] = new_capacity2
        new_row["Teacher Assigned"] = new_teacher
        
        # Add the new section to the DataFrame
        sections_df.loc[len(sections_df)] = new_row
        
        logger.info(f"Split section {section_id} into two sections: {section_id} ({new_capacity1} seats) and {new_section_id} ({new_capacity2} seats)")
    
    def _add_section(self, sections_df: pd.DataFrame, teachers_df: pd.DataFrame, 
                    section_id: str) -> None:
        """Add a new section based on an existing one"""
        # Check if section exists
        if not any(sections_df["Section ID"] == section_id):
            logger.warning(f"Section {section_id} not found in sections DataFrame")
            return
            
        # Get section information
        section = sections_df[sections_df["Section ID"] == section_id].iloc[0]
        course_id = section["Course ID"]
        department = section["Department"]
        
        # Create a new section ID (find the highest current section number and increment)
        section_numbers = []
        for s in sections_df["Section ID"]:
            if s.startswith("S"):
                # Remove the 'S' prefix and take only digits before any underscore
                base = s[1:].split('_')[0]
                try:
                    section_numbers.append(int(base))
                except ValueError:
                    # Skip if we can't convert to integer
                    pass
                
        new_section_num = max(section_numbers) + 1 if section_numbers else 1
        new_section_id = f"S{new_section_num:03d}"
        
        # Count sections per teacher
        teacher_counts = sections_df.groupby("Teacher Assigned").size().to_dict()
        
        # Find teachers who already teach this course
        qualified_teachers = sections_df[sections_df["Course ID"] == course_id]["Teacher Assigned"].unique()
        
        # Find potential teachers who:
        # 1. Already teach this course
        # 2. Have fewer than 6 sections
        potential_teachers = []
        for teacher in qualified_teachers:
            if teacher_counts.get(teacher, 0) < 6:
                potential_teachers.append(teacher)
                
        if not potential_teachers:
            # Find teachers in same department with fewer than 6 sections
            dept_teachers = teachers_df[teachers_df["Department"] == department]["Teacher ID"].unique()
            for teacher in dept_teachers:
                if teacher_counts.get(teacher, 0) < 6:
                    potential_teachers.append(teacher)
                    
        if not potential_teachers:
            logger.warning(f"Cannot find teacher for new section of {course_id}")
            return
            
        # Set capacity based on department norms
        if department == "Special":
            capacity = 15
        elif department == "PE":
            capacity = 35
        elif department == "Science":
            capacity = 30
        else:  
            capacity = 25  # Default for other departments
        
        # Create new section with appropriate capacity
        new_row = section.copy()
        new_row["Section ID"] = new_section_id
        new_row["# of Seats Available"] = capacity
        new_row["Teacher Assigned"] = potential_teachers[0]
        
        # Add the new section to the original DataFrame directly
        sections_df.loc[len(sections_df)] = new_row
        
        logger.info(f"Added new section {new_section_id} for course {course_id} with capacity {capacity}, assigned to teacher {potential_teachers[0]}")
    
    def _save_final_results(self, schedule: Schedule, utilization_df: pd.DataFrame, output_dir: Path) -> None:
        """
        Save the final results of the optimization.
        
        Args:
            schedule: Final schedule
            utilization_df: Utilization report DataFrame
            output_dir: Directory to save final output files
        """
        # Save schedule files
        converter = DataConverter()
        
        # Convert schedule to DataFrames
        master_schedule_df = converter.convert_to_master_schedule_df(schedule)
        student_assignments_df = converter.convert_to_student_assignments_df(schedule)
        teacher_schedule_df = converter.convert_to_teacher_schedule_df(schedule)
        
        # Save DataFrames to CSV files
        master_schedule_df.to_csv(output_dir / "Master_Schedule.csv", index=False)
        student_assignments_df.to_csv(output_dir / "Student_Assignments.csv", index=False)
        teacher_schedule_df.to_csv(output_dir / "Teacher_Schedule.csv", index=False)
        utilization_df.to_csv(output_dir / "Utilization_Report.csv", index=False)
        
        # Create a summary report
        summary = {
            'total_sections': len(schedule.sections),
            'scheduled_sections': len([s for s in schedule.sections.values() if s.is_scheduled]),
            'total_assignments': len(schedule.assignments),
            'total_students': len(set(a.student_id for a in schedule.assignments)),
            'average_utilization': utilization_df['Utilization'].mean(),
            'min_utilization': utilization_df['Utilization'].min(),
            'max_utilization': utilization_df['Utilization'].max(),
            'underutilized_sections': len(utilization_df[utilization_df['Utilization'] < self.utilization_threshold]),
            'iterations': self.iteration + 1,
            'total_time': self.metrics['total_time']
        }
        
        # Save summary to JSON file
        with open(output_dir / "summary.json", "w") as f:
            json.dump(summary, f, indent=2)
        
        # Save HTML dashboard
        self._create_html_dashboard(schedule, utilization_df, summary, output_dir)
    
    def _create_html_dashboard(self, schedule: Schedule, utilization_df: pd.DataFrame, 
                             summary: Dict[str, Any], output_dir: Path) -> None:
        """
        Create an HTML dashboard with optimization results.
        
        Args:
            schedule: Final schedule
            utilization_df: Utilization report DataFrame
            summary: Summary statistics
            output_dir: Directory to save the dashboard
        """
        # Simple HTML template for the dashboard
        html = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <title>School Schedule Optimization Results</title>
            <style>
                body {{ font-family: Arial, sans-serif; margin: 0; padding: 20px; }}
                .container {{ max-width: 1200px; margin: 0 auto; }}
                .card {{ background: #f9f9f9; border-radius: 5px; padding: 20px; margin-bottom: 20px; box-shadow: 0 2px 5px rgba(0,0,0,0.1); }}
                .metric {{ display: inline-block; margin: 10px; padding: 15px; background: #fff; border-radius: 5px; box-shadow: 0 1px 3px rgba(0,0,0,0.1); min-width: 200px; }}
                .metric h3 {{ margin-top: 0; color: #333; }}
                .metric p {{ font-size: 24px; font-weight: bold; margin: 0; color: #0066cc; }}
                table {{ width: 100%; border-collapse: collapse; margin-top: 20px; }}
                th, td {{ padding: 10px; text-align: left; border-bottom: 1px solid #ddd; }}
                th {{ background-color: #f2f2f2; }}
                .chart {{ width: 100%; height: 300px; margin-top: 20px; }}
            </style>
        </head>
        <body>
            <div class="container">
                <h1>School Schedule Optimization Dashboard</h1>
                
                <div class="card">
                    <h2>Summary</h2>
                    <div class="metric">
                        <h3>Total Sections</h3>
                        <p>{summary['total_sections']}</p>
                    </div>
                    <div class="metric">
                        <h3>Scheduled Sections</h3>
                        <p>{summary['scheduled_sections']}</p>
                    </div>
                    <div class="metric">
                        <h3>Total Assignments</h3>
                        <p>{summary['total_assignments']}</p>
                    </div>
                    <div class="metric">
                        <h3>Total Students</h3>
                        <p>{summary['total_students']}</p>
                    </div>
                    <div class="metric">
                        <h3>Average Utilization</h3>
                        <p>{summary['average_utilization']:.2%}</p>
                    </div>
                    <div class="metric">
                        <h3>Min Utilization</h3>
                        <p>{summary['min_utilization']:.2%}</p>
                    </div>
                    <div class="metric">
                        <h3>Max Utilization</h3>
                        <p>{summary['max_utilization']:.2%}</p>
                    </div>
                    <div class="metric">
                        <h3>Underutilized Sections</h3>
                        <p>{summary['underutilized_sections']}</p>
                    </div>
                    <div class="metric">
                        <h3>Iterations</h3>
                        <p>{summary['iterations']}</p>
                    </div>
                    <div class="metric">
                        <h3>Total Time</h3>
                        <p>{summary['total_time']:.2f}s</p>
                    </div>
                </div>
                
                <div class="card">
                    <h2>Utilization Report</h2>
                    <table>
                        <tr>
                            <th>Section ID</th>
                            <th>Course ID</th>
                            <th>Capacity</th>
                            <th>Enrollment</th>
                            <th>Utilization</th>
                            <th>Status</th>
                        </tr>
                        {"".join(f"<tr><td>{row['Section ID']}</td><td>{row['Course ID']}</td><td>{row['Capacity']}</td><td>{row['Enrollment']}</td><td>{row['Utilization']:.2%}</td><td>{row['Status']}</td></tr>" for _, row in utilization_df.iterrows())}
                    </table>
                </div>
            </div>
        </body>
        </html>
        """
        
        # Save the HTML dashboard
        with open(output_dir / "dashboard.html", "w") as f:
            f.write(html)

# Main function to run the pipeline
def main():
    """
    Main function to run the optimization pipeline from command line.
    """
    parser = argparse.ArgumentParser(description="School Schedule Optimization Pipeline")
    parser.add_argument("--input_dir", type=str, required=True, help="Directory with input files")
    parser.add_argument("--output_dir", type=str, required=True, help="Directory for output files")
    parser.add_argument("--threshold", type=float, default=0.75, help="Minimum utilization threshold (0-1)")
    args = parser.parse_args()
    
    # Run the pipeline
    pipeline = OptimizationPipeline(
        input_dir=args.input_dir,
        output_dir=args.output_dir,
        utilization_threshold=args.threshold
    )
    
    results = pipeline.run()
    
    # Print summary
    print("\nOptimization Pipeline Complete!")
    print(f"Final results saved to: {results['output_dir']}")
    print(f"Total iterations: {results['iterations']}")
    print(f"Total time: {results['metrics']['total_time']:.2f} seconds")

if __name__ == "__main__":
    main()