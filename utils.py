import sys
import os

DARK_STYLE = """
    /* Black/Orange Theme */
    QWidget {
        background-color: #121212;
        color: #F0F0F0;
        outline: none;
    }
    QMainWindow { background-color: #1F1F1F; }
    #CustomTitleBar { background-color: #1F1F1F; }
    #CustomTitleBar QLabel { background-color: transparent; color: #F0F0F0; font-size: 18px; }
    #CustomTitleBar QPushButton { background-color: transparent; border: none; color: #F0F0F0; font-size: 18px; }
    #CustomTitleBar QPushButton:hover { background-color: #FFA64D; }
    QPushButton {
        background-color: #FF7F50; /* accent */
        border: 1px solid #FF7F50; /* accent */
        padding: 5px;
        border-radius: 6px;
        color: #000000;
    }
    QPushButton:hover {
        background-color: #121212; /* bg */
        color: #FF7F50; /* accent */
    }
    QPushButton[quickcast="true"] {
        background-color: #32CD32; /* LimeGreen */
        color: white;
    }
    QHeaderView::section {
        background-color: #1F1F1F;
        padding: 4px;
        border: 1px solid #FF7F50; /* accent */
        color: #F0F0F0;
    }
    QLineEdit, QTextEdit, QTableWidget, QListWidget {
        background-color: #1F1F1F;
        border: 1px solid #FF7F50; /* accent */
        border-radius: 6px;
    }
    QGroupBox {
        border: 1px solid #FF7F50; /* accent */
        border-radius: 8px;
        margin-top: 10px;
    }
    QGroupBox::title {
        subcontrol-origin: margin;
        subcontrol-position: top center;
        padding: 0 10px;
        font-weight: bold;
    }
    QCheckBox::indicator, QListView::indicator, QTableView::indicator {
        border: 1px solid #FF7F50; /* accent */
        border-radius: 3px;
        width: 13px;
        height: 13px;
    }
    QCheckBox::indicator:checked, QListView::indicator:checked, QTableView::indicator:checked {
        background-color: #FF7F50; /* accent */
        image: url(none); /* Hide the default checkmark */
    }
    QListView::indicator:checked, QTableView::indicator:checked {
        /* Make the checked state more obvious for list/table items */
        border: 1px solid #FF7F50;
        background-color: #FF7F50;
        image: url(none);
    }
"""

LIGHT_STYLE = """
    /* White/Pink Theme */
    QWidget { background-color: #FFFFFF; color: #000000; outline: none; }
    QMainWindow { background-color: #ECEFF4; }
    #CustomTitleBar { background-color: #FFFFFF; }
    #CustomTitleBar QLabel, #CustomTitleBar QPushButton { background-color: transparent; color: #000000; border: none; font-size: 18px; }
    #CustomTitleBar QPushButton:hover { background-color: #DA3A9D; }
    QPushButton {
        background-color: #FFC0CB; /* accent */
        border: 1px solid #FFC0CB; /* accent */
        padding: 5px;
        border-radius: 6px;
        color: #000000;
    }
    QPushButton:hover {
        background-color: #FFFFFF; /* bg */
        color: #DA3A9D;
    }
    QPushButton[quickcast="true"] {
        background-color: #32CD32; /* LimeGreen */
        color: white;
    }
    QHeaderView::section {
        background-color: #FFC0CB; /* accent */
        border: 1px solid #DA3A9D;
        color: #000000;
    }
    QLineEdit, QTextEdit, QTableWidget, QListWidget {
        border: 1px solid #DA3A9D;
        border-radius: 6px;
    }
    QGroupBox {
        border: 1px solid #DA3A9D;
        border-radius: 8px;
        margin-top: 10px;
    }
    QGroupBox::title {
        subcontrol-origin: margin;
        subcontrol-position: top center;
        padding: 0 10px;
        font-weight: bold;
    }
    QCheckBox::indicator, QListView::indicator, QTableView::indicator {
        border: 1px solid #DA3A9D;
        border-radius: 3px;
        width: 13px;
        height: 13px;
    }
    QCheckBox::indicator:checked, QListView::indicator:checked, QTableView::indicator:checked {
        background-color: #DA3A9D;
        image: url(none);
    }
    QListView::indicator:checked, QTableView::indicator:checked {
        /* Make the checked state more obvious for list/table items */
        border: 1px solid #DA3A9D;
        background-color: #DA3A9D;
        image: url(none);
    }
"""

FOREST_STYLE = """
    /* Black/Blue Theme */
    QWidget { background-color: #121212; color: #EAEAEA; outline: none; }
    QMainWindow { background-color: #1F1F1F; }
    #CustomTitleBar { background-color: #1F1F1F; }
    #CustomTitleBar QLabel, #CustomTitleBar QPushButton { color: #EAEAEA; background-color: transparent; border: none; font-size: 18px; }
    #CustomTitleBar QPushButton:hover { background-color: #4682B4; }
    QPushButton {
        background-color: #1E90FF; /* accent */
        border: 1px solid #1E90FF; /* accent */
        padding: 5px;
        border-radius: 6px;
    }
    QPushButton:hover {
        background-color: #121212; /* bg */
        color: #1E90FF; /* accent */
    }
    QPushButton[quickcast="true"] {
        background-color: #32CD32; /* LimeGreen */
        color: white;
    }
    QHeaderView::section { background-color: #1F1F1F; border: 1px solid #4169E1; }
    QLineEdit, QTextEdit, QTableWidget, QListWidget {
        background-color: #1F1F1F;
        border: 1px solid #4169E1;
        border-radius: 6px;
    }
    QGroupBox {
        border: 1px solid #4169E1;
        border-radius: 8px;
        margin-top: 10px;
    }
    QCheckBox::indicator, QListView::indicator, QTableView::indicator {
        border: 1px solid #1E90FF; /* accent */
        border-radius: 3px;
        width: 13px;
        height: 13px;
    }
    QCheckBox::indicator:checked, QListView::indicator:checked, QTableView::indicator:checked {
        background-color: #1E90FF; /* accent */
        image: url(none);
    }
    QListView::indicator:checked, QTableView::indicator:checked {
        /* Make the checked state more obvious for list/table items */
        border: 1px solid #1E90FF;
        background-color: #1E90FF;
        image: url(none);
    }
    QGroupBox::title { subcontrol-origin: margin; subcontrol-position: top center; padding: 0 10px; font-weight: bold; }
"""

OCEAN_STYLE = """
    /* White/Blue Theme */
    QWidget { background-color: #F0F8FF; color: #000080; outline: none; }
    QMainWindow { background-color: #F0F8FF; }
    #CustomTitleBar { background-color: #F0F8FF; }
    #CustomTitleBar QLabel, #CustomTitleBar QPushButton { color: #000080; background-color: transparent; border: none; font-size: 18px; }
    #CustomTitleBar QPushButton:hover { background-color: #87CEFA; }
    QPushButton {
        background-color: #87CEEB; /* accent */
        border: 1px solid #87CEEB; /* accent */
        padding: 5px;
        border-radius: 6px;
    }
    QPushButton:hover {
        background-color: #F0F8FF; /* bg */
        color: #000080;
    }
    QPushButton[quickcast="true"] {
        background-color: #32CD32; /* LimeGreen */
        color: white;
    }
    QHeaderView::section { background-color: #ADD8E6; border: 1px solid #87CEEB; }
    QLineEdit, QTextEdit, QTableWidget, QListWidget {
        border: 1px solid #87CEEB;
        border-radius: 6px;
    }
    QGroupBox {
        border: 1px solid #87CEEB;
        border-radius: 8px;
        margin-top: 10px;
    }
    QGroupBox::title { subcontrol-origin: margin; subcontrol-position: top center; padding: 0 10px; font-weight: bold; }
    QCheckBox::indicator, QListView::indicator, QTableView::indicator {
        border: 1px solid #000080;
        border-radius: 3px;
        width: 13px;
        height: 13px;
    }
    QCheckBox::indicator:checked, QListView::indicator:checked, QTableView::indicator:checked {
        background-color: #87CEEB; /* accent */
        image: url(none);
    }
    QListView::indicator:checked, QTableView::indicator:checked {
        /* Make the checked state more obvious for list/table items */
        border: 1px solid #87CEEB;
        background-color: #87CEEB;
        image: url(none);
    }
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