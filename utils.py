import sys
import os

DARK_STYLE = """
    /* Black/Orange Theme */
    QWidget {
        background-color: #121212;
        color: #F0F0F0;
        font-family: 'Segoe UI';
        font-size: 14px;
        outline: none;
    }
    QMainWindow { background-color: #1F1F1F; }
    #CustomTitleBar { background-color: #1F1F1F; }
    #CustomTitleBar QLabel { background-color: transparent; color: #F0F0F0; font-size: 16px; }
    #CustomTitleBar QPushButton { background-color: transparent; border: none; color: #F0F0F0; font-size: 16px; }
    #CustomTitleBar QPushButton:hover { background-color: #FFA64D; }
    QPushButton {
        background-color: #FF7F50;
        border: 1px solid #444444;
        padding: 5px;
        border-radius: 6px;
        color: #000000;
    }
    QHeaderView::section {
        background-color: #1F1F1F;
        padding: 4px;
        border: 1px solid #444444;
        color: #F0F0F0;
    }
"""

LIGHT_STYLE = """
    /* White/Pink Theme */
    QWidget { background-color: #FFFFFF; color: #000000; font-family: 'Segoe UI'; font-size: 14px; outline: none; }
    QMainWindow { background-color: #ECEFF4; }
    #CustomTitleBar { background-color: #FFFFFF; }
    #CustomTitleBar QLabel, #CustomTitleBar QPushButton { background-color: transparent; color: #000000; border: none; font-size: 16px; }
    #CustomTitleBar QPushButton:hover { background-color: #DA3A9D; }
    QPushButton {
        background-color: #FFC0CB;
        border: 1px solid #E6A8B8;
        padding: 5px;
        border-radius: 6px;
        color: #000000;
    }
    QHeaderView::section { background-color: #FFC0CB; border: 1px solid #E6A8B8; color: #000000; }
"""

FOREST_STYLE = """
    /* Black/Blue Theme */
    QWidget { background-color: #121212; color: #EAEAEA; font-family: 'Segoe UI'; font-size: 14px; outline: none; }
    QMainWindow { background-color: #1F1F1F; }
    #CustomTitleBar { background-color: #1F1F1F; }
    #CustomTitleBar QLabel, #CustomTitleBar QPushButton { color: #EAEAEA; background-color: transparent; border: none; font-size: 16px; }
    #CustomTitleBar QPushButton:hover { background-color: #4682B4; }
    QPushButton { background-color: #1E90FF; border: 1px solid #4169E1; padding: 5px; border-radius: 6px; }
    QHeaderView::section { background-color: #1F1F1F; border: 1px solid #4169E1; }
"""

OCEAN_STYLE = """
    /* White/Blue Theme */
    QWidget { background-color: #F0F8FF; color: #000080; font-family: 'Segoe UI'; font-size: 14px; outline: none; }
    QMainWindow { background-color: #F0F8FF; }
    #CustomTitleBar { background-color: #F0F8FF; }
    #CustomTitleBar QLabel, #CustomTitleBar QPushButton { color: #000080; background-color: transparent; border: none; font-size: 16px; }
    #CustomTitleBar QPushButton:hover { background-color: #87CEFA; }
    QPushButton { background-color: #87CEEB; border: 1px solid #4682B4; padding: 5px; border-radius: 6px; }
    QHeaderView::section { background-color: #ADD8E6; border: 1px solid #87CEEB; }
"""

def get_base_path():
    """ Get absolute path to resource, works for dev and for PyInstaller/Nuitka """
    if getattr(sys, 'frozen', False):
        # The application is frozen
        return os.path.dirname(sys.executable)
    else:
        # The application is not frozen
        # Change this to the directory of your main script
        return os.path.dirname(os.path.abspath(__file__))