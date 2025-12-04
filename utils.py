import sys
import os

def get_base_path():
    """ Get absolute path to resource, works for dev and for PyInstaller/Nuitka """
    if getattr(sys, 'frozen', False):
        # If the application is run as a bundle, the base path is the directory
        # where the executable is located.
        return os.path.dirname(sys.executable)
    else:
        # The application is not frozen
        # Change this to the directory of your main script
        return os.path.dirname(os.path.abspath(__file__))