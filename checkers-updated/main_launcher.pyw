import sys
import os

# Redirect stdout/stderr to logs.txt for debugging
log_file = open("logs.txt", "w", buffering=1)  # line-buffered
sys.stdout = log_file
sys.stderr = log_file
print("--- Checkers Session Started ---")

# Change to the script directory
os.chdir(os.path.dirname(os.path.abspath(__file__)))

# Import and run main
if __name__ == '__main__':
    import main
