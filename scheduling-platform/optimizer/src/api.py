"""
REST API for the school scheduling optimizer.
Provides HTTP endpoints to run the optimizer and manage scheduling jobs.
"""
import os
import shutil
import tempfile
import uuid
import json
import logging
import time
from typing import Dict, List, Any, Optional
from pathlib import Path
from flask import Flask, request, jsonify, send_file, abort
from flask_cors import CORS
from werkzeug.utils import secure_filename
from threading import Thread

from .optimizer import ScheduleOptimizer

# Configure logging
logging.basicConfig(level=logging.INFO,
                   format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Create Flask app
app = Flask(__name__)
CORS(app)  # Enable CORS for all routes

# Configure app
app.config['UPLOAD_FOLDER'] = os.environ.get('UPLOAD_FOLDER', '/tmp/optimizer/uploads')
app.config['RESULTS_FOLDER'] = os.environ.get('RESULTS_FOLDER', '/tmp/optimizer/results')
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16 MB limit

# Create directories if they don't exist
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
os.makedirs(app.config['RESULTS_FOLDER'], exist_ok=True)

# Dictionary to store optimization jobs
jobs = {}


@app.route('/api/v1/health', methods=['GET'])
def health_check():
    """Health check endpoint."""
    return jsonify({
        'status': 'healthy',
        'timestamp': time.time()
    })


@app.route('/api/v1/jobs', methods=['GET'])
def list_jobs():
    """List optimization jobs."""
    return jsonify({
        'jobs': list(jobs.values())
    })


@app.route('/api/v1/jobs/<job_id>', methods=['GET'])
def get_job(job_id):
    """Get details of a specific job."""
    if job_id not in jobs:
        abort(404, description=f"Job {job_id} not found")
    
    return jsonify(jobs[job_id])


@app.route('/api/v1/jobs/<job_id>/download/<file_type>', methods=['GET'])
def download_result(job_id, file_type):
    """Download a result file from a job."""
    if job_id not in jobs:
        abort(404, description=f"Job {job_id} not found")
    
    job = jobs[job_id]
    
    if job['status'] != 'completed':
        abort(400, description=f"Job {job_id} is not completed")
    
    file_mapping = {
        'master_schedule': 'Master_Schedule.csv',
        'student_assignments': 'Student_Assignments.csv',
        'teacher_schedule': 'Teacher_Schedule.csv',
        'utilization_report': 'Utilization_Report.csv'
    }
    
    if file_type not in file_mapping:
        abort(400, description=f"Invalid file type: {file_type}")
    
    file_name = file_mapping[file_type]
    file_path = os.path.join(job['output_dir'], file_name)
    
    if not os.path.exists(file_path):
        abort(404, description=f"File {file_name} not found")
    
    return send_file(file_path, 
                    mimetype='text/csv',
                    as_attachment=True,
                    download_name=file_name)


def run_optimization_job(job_id: str, input_dir: str, output_dir: str, algorithm: str):
    """Run an optimization job in a separate thread."""
    try:
        # Update job status
        jobs[job_id]['status'] = 'processing'
        
        # Create optimizer
        optimizer = ScheduleOptimizer(
            input_dir=input_dir,
            output_dir=output_dir
        )
        
        # Run optimization
        results = optimizer.optimize(algorithm=algorithm)
        
        # Update job with results
        jobs[job_id].update({
            'status': 'completed' if results['success'] else 'failed',
            'results': results,
            'completed_at': time.time()
        })
        
        logger.info(f"Job {job_id} completed with status: {jobs[job_id]['status']}")
        
    except Exception as e:
        logger.error(f"Error in job {job_id}: {str(e)}")
        
        # Update job with error
        jobs[job_id].update({
            'status': 'failed',
            'error': str(e),
            'completed_at': time.time()
        })


@app.route('/api/v1/optimize', methods=['POST'])
def optimize():
    """Submit a new optimization job."""
    # Check if files are provided
    if 'files' not in request.files:
        abort(400, description="No files provided")
    
    files = request.files.getlist('files')
    if not files:
        abort(400, description="No files selected")
    
    # Get algorithm parameter
    algorithm = request.form.get('algorithm', 'greedy')
    if algorithm not in ['greedy', 'milp']:
        abort(400, description=f"Invalid algorithm: {algorithm}")
    
    # Create job ID and directories
    job_id = str(uuid.uuid4())
    job_input_dir = os.path.join(app.config['UPLOAD_FOLDER'], job_id)
    job_output_dir = os.path.join(app.config['RESULTS_FOLDER'], job_id)
    
    os.makedirs(job_input_dir, exist_ok=True)
    os.makedirs(job_output_dir, exist_ok=True)
    
    # Save uploaded files
    saved_files = []
    for file in files:
        if file.filename:
            filename = secure_filename(file.filename)
            file_path = os.path.join(job_input_dir, filename)
            file.save(file_path)
            saved_files.append({
                'name': filename,
                'path': file_path
            })
    
    # Create job record
    job = {
        'id': job_id,
        'status': 'pending',
        'algorithm': algorithm,
        'input_dir': job_input_dir,
        'output_dir': job_output_dir,
        'files': saved_files,
        'created_at': time.time(),
        'started_at': None,
        'completed_at': None
    }
    
    jobs[job_id] = job
    
    # Start optimization in a separate thread
    job['started_at'] = time.time()
    thread = Thread(target=run_optimization_job, 
                   args=(job_id, job_input_dir, job_output_dir, algorithm))
    thread.start()
    
    # Return job details
    return jsonify({
        'job_id': job_id,
        'status': 'pending',
        'message': 'Optimization job submitted successfully'
    }), 202  # 202 Accepted


@app.route('/api/v1/jobs/<job_id>', methods=['DELETE'])
def delete_job(job_id):
    """Delete a job and its files."""
    if job_id not in jobs:
        abort(404, description=f"Job {job_id} not found")
    
    job = jobs[job_id]
    
    # Only allow deleting completed or failed jobs
    if job['status'] not in ['completed', 'failed']:
        abort(400, description=f"Cannot delete job {job_id} with status {job['status']}")
    
    # Delete job directories
    if os.path.exists(job['input_dir']):
        shutil.rmtree(job['input_dir'])
    
    if os.path.exists(job['output_dir']):
        shutil.rmtree(job['output_dir'])
    
    # Remove job from dictionary
    del jobs[job_id]
    
    return jsonify({
        'message': f"Job {job_id} deleted successfully"
    })


def create_app():
    """Create the Flask application."""
    return app


if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)