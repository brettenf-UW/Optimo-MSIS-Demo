#!/usr/bin/env python3
"""
School Schedule Optimization Pipeline

This module provides the OptimizationPipeline class that coordinates the multi-stage
optimization process:
1. Data loading with validation
2. Greedy algorithm for initial solution
3. MILP optimization for refined solution
4. Claude agent for section adjustment
5. Iterative improvement until utilization targets are met
"""
import os
import time
import json
import logging
import shutil
from pathlib import Path
from typing import Dict, List, Any, Optional
import pandas as pd
import datetime

# Import the components from our algorithms
from .algorithms.load import ScheduleDataLoader
from .algorithms.greedy import load_data as greedy_load_data
from .algorithms.greedy import preprocess_data, greedy_schedule_sections, greedy_assign_students
from .algorithms.milp_soft import ScheduleOptimizer
from .algorithms.schedule_optimizer import UtilizationOptimizer

# Configure logging
logger = logging.getLogger(__name__)

class OptimizationPipeline:
    """
    Orchestrates the multi-stage school scheduling optimization process,
    integrating greedy initial solutions, MILP optimization, and Claude agent 
    section adjustments.
    """
    
    def __init__(self, input_dir: Path, output_dir: Path, utilization_threshold: float = 0.75):
        """
        Initialize the optimization pipeline.
        
        Args:
            input_dir: Directory containing input CSV files
            output_dir: Directory to save output files
            utilization_threshold: Minimum section utilization (0.0-1.0)
        """
        self.input_dir = Path(input_dir)
        self.output_dir = Path(output_dir)
        self.utilization_threshold = utilization_threshold
        self.max_iterations = 5
        self.metrics = {
            "greedy_time": 0,
            "milp_time": 0,
            "agent_time": 0,
            "total_time": 0
        }
        
        # Create output directory
        self.output_dir.mkdir(parents=True, exist_ok=True)
        
        # Setup iterations subdirectory
        self.iterations_dir = self.output_dir / "iterations"
        self.iterations_dir.mkdir(parents=True, exist_ok=True)
        
        # Setup final output directory
        self.final_dir = self.output_dir / "final"
        self.final_dir.mkdir(parents=True, exist_ok=True)

    def _prepare_iteration_directory(self, iteration: int) -> Path:
        """
        Prepare directory for the current iteration.
        
        Args:
            iteration: Current iteration number
            
        Returns:
            Path to the iteration directory
        """
        iteration_dir = self.iterations_dir / f"iteration_{iteration}"
        iteration_dir.mkdir(parents=True, exist_ok=True)
        
        # Create new_inputs directory for the next iteration
        new_inputs_dir = iteration_dir / "new_inputs"
        new_inputs_dir.mkdir(parents=True, exist_ok=True)
        
        # Create debug directory
        debug_dir = new_inputs_dir / "debug"
        debug_dir.mkdir(parents=True, exist_ok=True)
        
        return iteration_dir

    def _copy_input_files(self, source_dir: Path, dest_dir: Path):
        """
        Copy input CSV files to the destination directory.
        
        Args:
            source_dir: Source directory containing input files
            dest_dir: Destination directory
        """
        # Ensure destination directory exists
        dest_dir.mkdir(parents=True, exist_ok=True)
        
        # List of input file names
        input_files = [
            "Period.csv",
            "Sections_Information.csv", 
            "Student_Info.csv",
            "Student_Preference_Info.csv",
            "Teacher_Info.csv",
            "Teacher_unavailability.csv"
        ]
        
        # Copy each file if it exists
        for filename in input_files:
            source_file = source_dir / filename
            if source_file.exists():
                shutil.copy2(source_file, dest_dir / filename)
                logger.info(f"Copied {filename} to {dest_dir}")
            else:
                logger.warning(f"Input file {filename} not found in {source_dir}")

    def _get_section_utilization(self, student_assignments: pd.DataFrame, 
                                sections: pd.DataFrame) -> Dict[str, float]:
        """
        Calculate the utilization of each section.
        
        Args:
            student_assignments: DataFrame with student assignments
            sections: DataFrame with section information
            
        Returns:
            Dictionary mapping section IDs to utilization ratios
        """
        section_counts = student_assignments.groupby('Section ID').size()
        section_capacities = sections.set_index('Section ID')['# of Seats Available']
        
        utilization = {}
        for section_id in sections['Section ID']:
            enrolled = section_counts.get(section_id, 0)
            capacity = section_capacities.get(section_id, 1)  # Default to 1 to avoid division by zero
            utilization[section_id] = enrolled / capacity
            
        return utilization

    def _check_utilization_target(self, utilization: Dict[str, float]) -> bool:
        """
        Check if all sections meet the utilization target.
        
        Args:
            utilization: Dictionary mapping section IDs to utilization ratios
            
        Returns:
            True if all sections meet the target, False otherwise
        """
        below_threshold = {
            section_id: util 
            for section_id, util in utilization.items() 
            if util < self.utilization_threshold
        }
        
        if below_threshold:
            logger.info(f"{len(below_threshold)} sections below utilization threshold:")
            for section_id, util in below_threshold.items():
                logger.info(f"  {section_id}: {util:.2%}")
            return False
        else:
            logger.info("All sections meet utilization target!")
            return True

    def _create_dashboard(self, final_dir: Path, metrics: Dict):
        """
        Create an HTML dashboard with visualization of results.
        
        Args:
            final_dir: Directory containing final results
            metrics: Performance metrics dictionary
        """
        try:
            # Load final data
            master_schedule = pd.read_csv(final_dir / "Master_Schedule.csv")
            student_assignments = pd.read_csv(final_dir / "Student_Assignments.csv")
            teacher_schedule = pd.read_csv(final_dir / "Teacher_Schedule.csv")
            utilization_report = pd.read_csv(final_dir / "Utilization_Report.csv")
            
            # Create an HTML dashboard
            html = f"""
            <!DOCTYPE html>
            <html lang="en">
            <head>
                <meta charset="UTF-8">
                <meta name="viewport" content="width=device-width, initial-scale=1.0">
                <title>School Schedule Optimization Results</title>
                <style>
                    body {{ font-family: Arial, sans-serif; margin: 0; padding: 20px; }}
                    .dashboard {{ max-width: 1200px; margin: 0 auto; }}
                    .summary {{ background-color: #f5f5f5; padding: 20px; border-radius: 5px; margin-bottom: 20px; }}
                    .metrics {{ display: flex; flex-wrap: wrap; gap: 20px; margin-bottom: 20px; }}
                    .metric-card {{ background-color: #fff; border: 1px solid #ddd; border-radius: 5px; padding: 15px; flex: 1; min-width: 200px; }}
                    .metric-value {{ font-size: 24px; font-weight: bold; margin-top: 10px; }}
                    h1, h2, h3 {{ color: #2c3e50; }}
                    table {{ width: 100%; border-collapse: collapse; margin-bottom: 20px; }}
                    th, td {{ border: 1px solid #ddd; padding: 8px; text-align: left; }}
                    th {{ background-color: #f2f2f2; }}
                    tr:nth-child(even) {{ background-color: #f9f9f9; }}
                </style>
            </head>
            <body>
                <div class="dashboard">
                    <h1>School Schedule Optimization Results</h1>
                    
                    <div class="summary">
                        <h2>Summary</h2>
                        <p>Generated on {datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")}</p>
                        <p>Total iterations: {metrics.get("iterations", "N/A")}</p>
                        <p>Total runtime: {metrics.get("total_time", 0):.2f} seconds</p>
                    </div>
                    
                    <div class="metrics">
                        <div class="metric-card">
                            <h3>Sections</h3>
                            <div class="metric-value">{len(master_schedule)}</div>
                        </div>
                        <div class="metric-card">
                            <h3>Students Assigned</h3>
                            <div class="metric-value">{len(student_assignments["Student ID"].unique())}</div>
                        </div>
                        <div class="metric-card">
                            <h3>Total Assignments</h3>
                            <div class="metric-value">{len(student_assignments)}</div>
                        </div>
                        <div class="metric-card">
                            <h3>Average Utilization</h3>
                            <div class="metric-value">{utilization_report["Utilization"].mean():.2%}</div>
                        </div>
                    </div>
                    
                    <h2>Utilization Report</h2>
                    <table>
                        <tr>
                            <th>Section ID</th>
                            <th>Course ID</th>
                            <th>Capacity</th>
                            <th>Enrolled</th>
                            <th>Utilization</th>
                        </tr>
            """
            
            # Add utilization report rows
            for _, row in utilization_report.iterrows():
                html += f"""
                        <tr>
                            <td>{row.get("Section ID", "")}</td>
                            <td>{row.get("Course ID", "")}</td>
                            <td>{int(row.get("Capacity", 0))}</td>
                            <td>{int(row.get("Enrolled", 0))}</td>
                            <td>{float(row.get("Utilization", 0)):.2%}</td>
                        </tr>
                """
                
            html += """
                    </table>
                    
                    <h2>Performance Metrics</h2>
                    <table>
                        <tr>
                            <th>Component</th>
                            <th>Time (seconds)</th>
                            <th>Percentage</th>
                        </tr>
            """
            
            # Add performance metrics
            total_time = metrics.get("total_time", 0)
            if total_time > 0:
                for component, time_value in metrics.items():
                    if component != "total_time" and component != "iterations":
                        percentage = (time_value / total_time) * 100
                        html += f"""
                            <tr>
                                <td>{component.replace("_time", "").title()}</td>
                                <td>{time_value:.2f}</td>
                                <td>{percentage:.2f}%</td>
                            </tr>
                        """
                        
            html += """
                    </table>
                </div>
            </body>
            </html>
            """
            
            # Write dashboard to file
            with open(final_dir / "dashboard.html", "w") as f:
                f.write(html)
                
            logger.info(f"Dashboard generated at {final_dir / 'dashboard.html'}")
            
        except Exception as e:
            logger.error(f"Error creating dashboard: {str(e)}")

    def _create_utilization_report(self, sections_file: Path, assignments_file: Path, 
                                 output_file: Path):
        """
        Create a utilization report for all sections.
        
        Args:
            sections_file: Path to the sections CSV file
            assignments_file: Path to the student assignments CSV file
            output_file: Path to save the utilization report
        """
        try:
            # Load data
            sections = pd.read_csv(sections_file)
            assignments = pd.read_csv(assignments_file)
            
            # Calculate enrollment for each section
            enrollment = assignments.groupby('Section ID').size().reset_index(name='Enrolled')
            
            # Merge with sections data
            utilization = pd.merge(
                sections[['Section ID', 'Course ID', '# of Seats Available']], 
                enrollment,
                on='Section ID',
                how='left'
            )
            
            # Fill missing values with 0
            utilization['Enrolled'] = utilization['Enrolled'].fillna(0)
            
            # Calculate utilization ratio
            utilization['Utilization'] = utilization['Enrolled'] / utilization['# of Seats Available']
            
            # Rename columns for clarity
            utilization = utilization.rename(columns={'# of Seats Available': 'Capacity'})
            
            # Save to file
            utilization.to_csv(output_file, index=False)
            logger.info(f"Utilization report saved to {output_file}")
            
            return utilization
            
        except Exception as e:
            logger.error(f"Error creating utilization report: {str(e)}")
            return None

    def run(self) -> Dict:
        """
        Run the optimization pipeline.
        
        Returns:
            Dictionary with results and performance metrics
        """
        start_time = time.time()
        logger.info(f"Starting optimization pipeline with input directory: {self.input_dir}")
        logger.info(f"Output directory: {self.output_dir}")
        logger.info(f"Utilization threshold: {self.utilization_threshold:.2%}")
        
        current_input_dir = self.input_dir
        iteration = 0
        all_iterations_complete = False
        
        # Initialize metrics.json
        metrics_file = self.output_dir / "metrics.json"
        
        try:
            while iteration < self.max_iterations and not all_iterations_complete:
                iteration += 1
                logger.info(f"\n{'='*50}\nStarting iteration {iteration}/{self.max_iterations}\n{'='*50}")
                
                # Prepare iteration directory
                iteration_dir = self._prepare_iteration_directory(iteration)
                
                # Stage 1: Use our ScheduleDataLoader to load data
                logger.info(f"Stage 1: Loading data from {current_input_dir}")
                loader_start = time.time()
                
                # Adjust working directory for file loading
                original_dir = os.getcwd()
                os.chdir(current_input_dir.parent)
                
                # Create a data loader
                try:
                    # Use the ScheduleDataLoader from load.py
                    data_loader = ScheduleDataLoader()
                    
                    # Directly set the input_dir to our current_input_dir
                    data_loader.input_dir = current_input_dir
                    
                    # Load all data
                    data = data_loader.load_all()
                    
                    logger.info(f"Data loaded successfully from {current_input_dir}")
                except Exception as e:
                    logger.error(f"Error loading data with ScheduleDataLoader: {str(e)}")
                    logger.info("Falling back to greedy loader...")
                    
                    # Fall back to greedy loader
                    students, student_preferences, teachers, sections, teacher_unavailability, periods = greedy_load_data(str(current_input_dir))
                    
                    # Create data dict manually
                    data = {
                        'students': students,
                        'student_preferences': student_preferences,
                        'teachers': teachers,
                        'sections': sections,
                        'teacher_unavailability': teacher_unavailability,
                        'periods': periods
                    }
                    
                    logger.info("Data loaded successfully with fallback method")
                
                # Restore working directory
                os.chdir(original_dir)
                
                loader_time = time.time() - loader_start
                logger.info(f"Data loading completed in {loader_time:.2f} seconds")
                
                # Stage 2: Run greedy algorithm
                logger.info("Stage 2: Running greedy algorithm for initial solution")
                greedy_start = time.time()
                
                # Preprocess data
                processed_data = preprocess_data(
                    data['students'], 
                    data['student_preferences'], 
                    data['teachers'], 
                    data['sections'], 
                    data['teacher_unavailability'],
                    data.get('periods', ['R1', 'R2', 'R3', 'R4', 'G1', 'G2', 'G3', 'G4'])
                )
                
                # Schedule sections to periods
                scheduled_sections = greedy_schedule_sections(data['sections'], processed_data['periods'], processed_data)
                
                # Assign students to sections
                student_assignments = greedy_assign_students(data['students'], scheduled_sections, processed_data)
                
                # Convert to DataFrames for saving
                master_schedule_df = pd.DataFrame([
                    {'Section ID': section_id, 'Period': period}
                    for section_id, period in scheduled_sections.items()
                ])
                
                student_assignments_df = pd.DataFrame([
                    {'Student ID': student_id, 'Section ID': section_id}
                    for student_id, section_ids in student_assignments.items()
                    for section_id in section_ids
                ])
                
                # Save results
                master_schedule_df.to_csv(iteration_dir / "Master_Schedule.csv", index=False)
                student_assignments_df.to_csv(iteration_dir / "Student_Assignments.csv", index=False)
                
                # Create teacher schedule
                section_to_teacher = data['sections'].set_index('Section ID')['Teacher Assigned'].to_dict()
                teacher_schedule_df = pd.DataFrame([
                    {'Teacher ID': section_to_teacher[section_id], 
                     'Section ID': section_id, 
                     'Period': period}
                    for section_id, period in scheduled_sections.items()
                    if section_id in section_to_teacher
                ])
                teacher_schedule_df.to_csv(iteration_dir / "Teacher_Schedule.csv", index=False)
                
                # Create utilization report
                utilization_report = self._create_utilization_report(
                    current_input_dir / "Sections_Information.csv",
                    iteration_dir / "Student_Assignments.csv",
                    iteration_dir / "Utilization_Report.csv"
                )
                
                greedy_time = time.time() - greedy_start
                self.metrics["greedy_time"] += greedy_time
                logger.info(f"Greedy algorithm completed in {greedy_time:.2f} seconds")
                
                # Stage 3: Run MILP optimization with Gurobi
                logger.info("Stage 3: Running MILP optimization with Gurobi")
                milp_start = time.time()
                
                try:
                    # Create a temporary directory structure for the MILP optimizer
                    milp_input_dir = iteration_dir / "milp_input"
                    milp_input_dir.mkdir(parents=True, exist_ok=True)
                    
                    # Copy the necessary files
                    self._copy_input_files(current_input_dir, milp_input_dir)
                    
                    # If Greedy output exists, copy it to MILP input
                    if (iteration_dir / "Master_Schedule.csv").exists():
                        shutil.copy2(iteration_dir / "Master_Schedule.csv", milp_input_dir / "Master_Schedule.csv")
                    if (iteration_dir / "Student_Assignments.csv").exists():
                        shutil.copy2(iteration_dir / "Student_Assignments.csv", milp_input_dir / "Student_Assignments.csv")
                    if (iteration_dir / "Teacher_Schedule.csv").exists():
                        shutil.copy2(iteration_dir / "Teacher_Schedule.csv", milp_input_dir / "Teacher_Schedule.csv")
                    
                    # Adjust working directory temporarily
                    original_dir = os.getcwd()
                    os.chdir(str(milp_input_dir.parent))
                    
                    # Initialize the MILP optimizer with our custom input directory
                    from .algorithms.milp_soft import ScheduleOptimizer
                    
                    # Create the optimizer with the input directory
                    optimizer = ScheduleOptimizer(input_dir=milp_input_dir)
                    
                    # Create variables, constraints, and solve
                    optimizer.create_variables()
                    optimizer.add_constraints()
                    optimizer.set_objective()
                    optimizer.greedy_initial_solution()  # Use greedy warm start
                    optimizer.solve()
                    
                    # Copy the MILP output to the iteration directory
                    if os.path.exists(str(milp_input_dir / "output")):
                        milp_output_files = ["Master_Schedule.csv", "Student_Assignments.csv", "Teacher_Schedule.csv"]
                        for file in milp_output_files:
                            if os.path.exists(str(milp_input_dir / "output" / file)):
                                shutil.copy2(
                                    str(milp_input_dir / "output" / file),
                                    str(iteration_dir / file)
                                )
                                logger.info(f"Copied MILP output {file} to iteration directory")
                    
                    # Restore working directory
                    os.chdir(original_dir)
                    
                    logger.info("MILP optimization completed successfully")
                except Exception as e:
                    logger.error(f"Error running MILP optimization: {str(e)}")
                    logger.error("Stack trace:", exc_info=True)
                    logger.warning("Continuing pipeline with greedy solution only")
                
                milp_time = time.time() - milp_start
                self.metrics["milp_time"] += milp_time
                logger.info(f"MILP optimization completed in {milp_time:.2f} seconds")
                
                # Check if we need to run the Claude agent (only if we have utilization below threshold)
                need_claude_agent = False
                
                # Create/update the utilization report if it doesn't exist
                if not (iteration_dir / "Utilization_Report.csv").exists():
                    utilization_report = self._create_utilization_report(
                        current_input_dir / "Sections_Information.csv",
                        iteration_dir / "Student_Assignments.csv",
                        iteration_dir / "Utilization_Report.csv"
                    )
                else:
                    utilization_report = pd.read_csv(iteration_dir / "Utilization_Report.csv")
                
                # Check if any sections have utilization below threshold
                if utilization_report is not None:
                    low_utilization_sections = utilization_report[
                        utilization_report['Utilization'] < self.utilization_threshold
                    ]
                    need_claude_agent = len(low_utilization_sections) > 0
                    
                    if need_claude_agent:
                        logger.info(f"Found {len(low_utilization_sections)} sections below {self.utilization_threshold:.2%} utilization")
                        for _, row in low_utilization_sections.iterrows():
                            logger.info(f"  {row['Section ID']}: {row['Utilization']:.2%}")
                    else:
                        logger.info(f"All sections meet the {self.utilization_threshold:.2%} utilization target!")
                        
                # Stage 4: Run Claude agent for section adjustments if needed
                if need_claude_agent:
                    logger.info("Stage 4: Running Claude agent for section adjustments")
                    agent_start = time.time()
                    
                    # Use the provided Claude API key
                    api_key = "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"
                    
                    try:
                        # Set up the utilization optimizer with the Claude API key
                        optimizer = UtilizationOptimizer(api_key)
                        
                        # Update paths to match our current directory structure
                        optimizer.input_path = current_input_dir
                        optimizer.output_path = iteration_dir
                        
                        # Run the optimization, passing the current iteration number
                        # This helps Claude understand context and make unique changes each iteration
                        optimizer.optimize(iteration=iteration)
                        
                        logger.info(f"Claude agent completed successfully on iteration {iteration}")
                    except Exception as e:
                        logger.error(f"Error running Claude agent: {str(e)}")
                        logger.error(f"Stack trace: ", exc_info=True)
                    
                    agent_time = time.time() - agent_start
                    self.metrics["agent_time"] += agent_time
                    logger.info(f"Claude agent completed in {agent_time:.2f} seconds")
                else:
                    logger.info("Skipping Claude agent as all sections meet utilization target")
                
                # Check if we've met the utilization target
                if utilization_report is not None:
                    utilization_dict = dict(zip(
                        utilization_report['Section ID'],
                        utilization_report['Utilization']
                    ))
                    
                    all_iterations_complete = self._check_utilization_target(utilization_dict)
                    if all_iterations_complete:
                        logger.info("Utilization target met! Stopping iterations.")
                    else:
                        logger.info("Utilization target not met. Continuing to next iteration.")
                
                # Set up input for the next iteration
                next_input_dir = iteration_dir / "new_inputs"
                self._copy_input_files(current_input_dir, next_input_dir)
                
                # CRITICAL: Copy the latest output files to the new input directory for next iteration
                # Copy Master_Schedule.csv to be used by the next iteration
                if (iteration_dir / "Master_Schedule.csv").exists():
                    logger.info("Using Master_Schedule.csv from the current iteration")
                    shutil.copy2(iteration_dir / "Master_Schedule.csv", next_input_dir / "Master_Schedule.csv")
                
                # Copy Student_Assignments.csv to be used by the next iteration
                if (iteration_dir / "Student_Assignments.csv").exists():
                    logger.info("Using Student_Assignments.csv from the current iteration")
                    shutil.copy2(iteration_dir / "Student_Assignments.csv", next_input_dir / "Student_Assignments.csv")
                
                # Copy Teacher_Schedule.csv to be used by the next iteration
                if (iteration_dir / "Teacher_Schedule.csv").exists():
                    logger.info("Using Teacher_Schedule.csv from the current iteration")
                    shutil.copy2(iteration_dir / "Teacher_Schedule.csv", next_input_dir / "Teacher_Schedule.csv")
                
                # Use updated Sections_Information.csv from the optimizer
                # The Claude agent should have modified this file
                # First check if Claude wrote the file to optimizer.input_path
                claude_updated_file = optimizer.input_path / "Sections_Information.csv"
                if claude_updated_file.exists():
                    logger.info("Using Claude-updated Sections_Information.csv for the next iteration")
                    shutil.copy2(claude_updated_file, next_input_dir / "Sections_Information.csv")
                # Fallback to current_input_dir if Claude didn't modify it
                elif (current_input_dir / "Sections_Information.csv").exists():
                    logger.info("Using existing Sections_Information.csv for the next iteration")
                    sections_file = current_input_dir / "Sections_Information.csv"
                    shutil.copy2(sections_file, next_input_dir / "Sections_Information.csv")
                
                # Move to the next iteration input directory
                current_input_dir = next_input_dir
            
            # Copy the final results to the final directory
            if iteration > 0:
                final_iteration_dir = self._prepare_iteration_directory(iteration)
                logger.info(f"Copying final results from iteration {iteration} to final directory")
                
                output_files = [
                    "Master_Schedule.csv",
                    "Student_Assignments.csv",
                    "Teacher_Schedule.csv",
                    "Utilization_Report.csv"
                ]
                
                # Ensure the final directory exists
                self.final_dir.mkdir(parents=True, exist_ok=True)
                
                # First try to copy from the last iteration directory
                files_copied = 0
                for filename in output_files:
                    source_file = final_iteration_dir / filename
                    if source_file.exists():
                        shutil.copy2(source_file, self.final_dir / filename)
                        logger.info(f"Copied {filename} to final directory")
                        files_copied += 1
                
                # If no files were copied, try from other iteration directories in reverse order
                if files_copied == 0:
                    logger.warning("No files found in the final iteration directory, looking in earlier iterations")
                    for i in range(iteration-1, 0, -1):
                        earlier_dir = self.iterations_dir / f"iteration_{i}"
                        if earlier_dir.exists():
                            for filename in output_files:
                                source_file = earlier_dir / filename
                                if source_file.exists() and not (self.final_dir / filename).exists():
                                    shutil.copy2(source_file, self.final_dir / filename)
                                    logger.info(f"Copied {filename} from iteration {i} to final directory")
                
                # Create final utilization report if it doesn't exist
                if not (self.final_dir / "Utilization_Report.csv").exists():
                    logger.info("Creating final utilization report")
                    if (self.final_dir / "Student_Assignments.csv").exists() and (current_input_dir / "Sections_Information.csv").exists():
                        self._create_utilization_report(
                            current_input_dir / "Sections_Information.csv",
                            self.final_dir / "Student_Assignments.csv",
                            self.final_dir / "Utilization_Report.csv"
                        )
                    else:
                        logger.warning("Could not create final utilization report - missing required files")
                
                # Create a summary.json file
                try:
                    # Check if all required files exist
                    has_master_schedule = (self.final_dir / "Master_Schedule.csv").exists()
                    has_student_assignments = (self.final_dir / "Student_Assignments.csv").exists()
                    has_teacher_schedule = (self.final_dir / "Teacher_Schedule.csv").exists()
                    
                    summary = {
                        "iterations": iteration,
                        "utilization_threshold": self.utilization_threshold,
                        "completion_time": datetime.datetime.now().isoformat()
                    }
                    
                    # Add metrics only if files exist
                    if has_master_schedule:
                        summary["sections"] = len(pd.read_csv(self.final_dir / "Master_Schedule.csv"))
                    
                    if has_student_assignments:
                        student_assignments_df = pd.read_csv(self.final_dir / "Student_Assignments.csv")
                        summary["students"] = len(student_assignments_df["Student ID"].unique())
                        summary["assignments"] = len(student_assignments_df)
                    
                    if has_teacher_schedule:
                        summary["teachers"] = len(pd.read_csv(self.final_dir / "Teacher_Schedule.csv")["Teacher ID"].unique())
                    
                    # Save the summary
                    with open(self.final_dir / "summary.json", "w") as f:
                        json.dump(summary, f, indent=2)
                    
                    logger.info("Created summary.json file")
                    
                    # Create an HTML dashboard
                    self._create_dashboard(self.final_dir, {**self.metrics, "iterations": iteration})
                    logger.info("Created HTML dashboard")
                    
                except Exception as e:
                    logger.error(f"Error creating summary files: {str(e)}")
                    logger.error("Stack trace:", exc_info=True)
            
            # Update the final metrics
            self.metrics["total_time"] = time.time() - start_time
            self.metrics["iterations"] = iteration
            
            # Save metrics.json
            with open(metrics_file, "w") as f:
                json.dump(self.metrics, f, indent=2)
            
            # Return results
            return {
                "success": True,
                "iterations": iteration,
                "output_dir": str(self.final_dir),
                "metrics": self.metrics
            }
            
        except Exception as e:
            logger.error(f"Error in optimization pipeline: {str(e)}", exc_info=True)
            
            # Update metrics with failure info
            self.metrics["total_time"] = time.time() - start_time
            self.metrics["error"] = str(e)
            
            # Save metrics.json even on failure
            with open(metrics_file, "w") as f:
                json.dump(self.metrics, f, indent=2)
            
            return {
                "success": False,
                "error": str(e),
                "metrics": self.metrics
            }


if __name__ == "__main__":
    # Example standalone usage
    input_dir = Path("Test Input Files/")
    output_dir = Path("output/")
    
    pipeline = OptimizationPipeline(
        input_dir=input_dir,
        output_dir=output_dir,
        utilization_threshold=0.75
    )
    
    results = pipeline.run()
    print(f"Pipeline completed with {'success' if results['success'] else 'failure'}")
    print(f"Results directory: {results.get('output_dir', 'N/A')}")
    print(f"Total iterations: {results.get('iterations', 0)}")
    print(f"Total runtime: {results.get('metrics', {}).get('total_time', 0):.2f} seconds")