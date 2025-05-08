import os
import shutil
import subprocess
import sys

def build():
    # Install PyInstaller if not already installed
    try:
        import PyInstaller
    except ImportError:
        print("Installing PyInstaller...")
        subprocess.check_call([sys.executable, "-m", "pip", "install", "pyinstaller"])

    # Clean up previous build
    if os.path.exists("build"):
        shutil.rmtree("build")
    if os.path.exists("dist"):
        shutil.rmtree("dist")
    if os.path.exists("release"):
        shutil.rmtree("release")

    # Run PyInstaller
    print("Building executable...")
    subprocess.check_call(["pyinstaller", "soda.spec"])

    # Create a directory for the final build
    os.makedirs("release")

    # Copy the executable and create a run script
    executable_path = "dist/soda"
    if os.path.exists(executable_path):
        shutil.copy(executable_path, "release/")
        
        # Create a run script
        with open("release/run.sh", "w") as f:
            f.write("""#!/bin/bash
# Set required environment variables
export FLASK_APP=./soda
export FLASK_ENV=production

# Run the application
./soda
""")
        os.chmod("release/run.sh", 0o755)

        print("\nBuild completed successfully!")
        print("The executable is located in the 'release' directory.")
        print("Run the application using: ./release/run.sh")
    else:
        print("Error: Executable not found at", executable_path)
        sys.exit(1)

if __name__ == "__main__":
    build() 