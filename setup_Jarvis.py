"""
Jarvis Environment Setup Script

This script handles the initial setup of the Jarvis application environment,
creating a virtual environment and installing dependencies.

Role in the system:
- Creates a Python virtual environment with proper version checking
- Installs required Python dependencies from requirements.txt
- Configures environment variables and paths
- Provides platform-specific setup instructions
- Guides users through manual dependency installation steps

This script should be run once when first setting up the Jarvis application
or when recreating the environment after significant changes.
"""

import subprocess
import sys
import os

def create_virtualenv():
    venv_dir = ".venv"

    # Determine Python executable based on OS
    if os.name == "nt":
        python_executable = "py"
        python_version_arg = "-3.11"
        python_check_cmd = [python_executable, python_version_arg, "--version"]
        python_venv_cmd = [python_executable, python_version_arg, "-m", "venv", venv_dir]
    else:
        python_executable = "python3.11"
        python_check_cmd = [python_executable, "--version"]
        python_venv_cmd = [python_executable, "-m", "venv", venv_dir]

    # Check Python version
    try:
        subprocess.run(python_check_cmd, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    except subprocess.CalledProcessError:
        print("Python 3.11 is not installed or not found in PATH.")
        print("Install it from https://www.python.org/downloads/release/python-3119/")
        sys.exit(1)
    except FileNotFoundError:
        print("Python launcher ('py') not found. Ensure Python is installed and added to PATH.")
        sys.exit(1)

    # Create virtual environment
    subprocess.run(python_venv_cmd, check=True)
    print(f"Virtual environment created at {venv_dir}")

    # Determine pip executable based on OS
    if os.name == "nt":
        activate_script = os.path.join(venv_dir, "Scripts", "activate.bat")
        pip_executable = os.path.join(venv_dir, "Scripts", "pip.exe")
    else:
        activate_script = os.path.join(venv_dir, "bin", "activate")
        pip_executable = os.path.join(venv_dir, "bin", "pip")

    # Add binaries to PATH in the activation script
    binaries_path = os.path.abspath("binaries")
    if os.name == "nt":
        activate_path = os.path.join(venv_dir, "Scripts", "activate.bat")
        with open(activate_path, "a") as f:
            f.write(f'\nset PATH={binaries_path};%PATH%\n')
    else:
        activate_path = os.path.join(venv_dir, "bin", "activate")
        with open(activate_path, "a") as f:
            f.write(f'\nexport PATH="{binaries_path}:$PATH"\n')

    # Install dependencies with real-time output
    print("Installing dependencies...")
    print("This may take a few minutes. Please do not interrupt.")
    try:
        subprocess.run([pip_executable, "install", "-r", "requirements.txt"], check=True)
    except subprocess.CalledProcessError as e:
        print(f"Dependency installation failed: {e}")
        sys.exit(1)

    print("Python dependencies installed successfully.\n")
    print("Please download and install the following dependencies manually:")
    #print("\n1. ffmpeg (https://ffmpeg.org/download.html)")  
    print("\n1. Ollama (https://ollama.com/download)")
    print("\nTo activate your virtual environment, open a new terminal and run:")
    if os.name == "nt":
        print(f"{activate_script}")
    else:
        print(f"source {activate_script}")
    print("\nThen run the main script:")
    if os.name == "nt":
        print("python start_Jarvis.py")
    else:
        print("python3 start_Jarvis.py")    

if __name__ == "__main__":
    create_virtualenv()