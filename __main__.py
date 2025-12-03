import tkinter as tk
from tkinter import messagebox
from .main import ImageEditorApp

if __name__ == "__main__":
    root = tk.Tk()
    app = ImageEditorApp(root)
    try:
        root.mainloop()
    except Exception as e:
        messagebox.showerror("Application Error", f"An error occurred: {e}")