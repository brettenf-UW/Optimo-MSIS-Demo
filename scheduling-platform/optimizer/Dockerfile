FROM python:3.9-slim

WORKDIR /app

# Install all dependencies
RUN apt-get update && apt-get install -y \
    build-essential \
    curl \
    wget \
    && rm -rf /var/lib/apt/lists/*

# Setup Gurobi
RUN mkdir -p /opt/gurobi

# Create a script to properly initialize Gurobi and run the command
# This handles setting up the license at runtime
RUN echo '#!/bin/bash\n\
export GUROBI_HOME=/opt/gurobi1000/linux64\n\
export PATH=$PATH:$GUROBI_HOME/bin\n\
export LD_LIBRARY_PATH=$GUROBI_HOME/lib:$LD_LIBRARY_PATH\n\
\n\
if [ ! -f /opt/gurobi/gurobi.lic ]; then\n\
    echo "Setting up Gurobi license..."\n\
    # Use Gurobi license key\n\
    echo "y" | grbgetkey ba446ea2-f2f6-4614-8e8f-aa378d1404b5\n\
fi\n\
\n\
# Execute the command passed to the script\n\
exec "$@"\n\
' > /entrypoint.sh && chmod +x /entrypoint.sh

# Download and extract Gurobi
RUN wget https://packages.gurobi.com/10.0/gurobi10.0.0_linux64.tar.gz && \
    tar -xf gurobi10.0.0_linux64.tar.gz -C /opt && \
    rm gurobi10.0.0_linux64.tar.gz

# Set Gurobi environment variables
ENV GUROBI_HOME=/opt/gurobi1000/linux64
ENV PATH=$PATH:$GUROBI_HOME/bin
ENV LD_LIBRARY_PATH=$LD_LIBRARY_PATH:$GUROBI_HOME/lib

# Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

EXPOSE 5000

# Set the entrypoint script
ENTRYPOINT ["/entrypoint.sh"]

# Default command
CMD ["python", "-m", "flask", "run", "--host=0.0.0.0", "--port=5000"]
