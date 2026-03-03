import sys
import os

# Suppress stdout/stderr to prevent console from showing
devnull = open(os.devnull, 'w')
sys.stdout = devnull
sys.stderr = devnull

# Change to the script directory
os.chdir(os.path.dirname(os.path.abspath(__file__)))

# Import and run main
if __name__ == '__main__':
    import main
