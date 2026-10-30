"""
PyInstaller build script for PDF Document Naming Tool.
Run with: python build_exe.py
Produces: dist/PDF_Document_Naming_Tool.exe
"""

import subprocess
import sys
import os

HERE = os.path.dirname(os.path.abspath(__file__))

# Collect all PySide6 Qt plugins needed for PDF rendering
PYINSTALLER_ARGS = [
    sys.executable, "-m", "PyInstaller",
    "--onefile",
    "--windowed",
    "--name", "PDF_Document_Naming_Tool",
    # Include Qt PDF plugins (needed at runtime for QPdfDocument/QPdfView)
    "--collect-all", "PySide6",
    # Hidden imports
    "--hidden-import", "PySide6.QtPdf",
    "--hidden-import", "PySide6.QtPdfWidgets",
    "--hidden-import", "PySide6.QtWidgets",
    "--hidden-import", "PySide6.QtCore",
    "--hidden-import", "PySide6.QtGui",
    "main.py",
]

if __name__ == "__main__":
    print("=" * 60)
    print("Building PDF Document Naming Tool .exe with PyInstaller")
    print("=" * 60)
    result = subprocess.run(PYINSTALLER_ARGS, cwd=HERE)
    if result.returncode == 0:
        dist_exe = os.path.join(HERE, "dist", "PDF_Document_Naming_Tool.exe")
        print()
        print("=" * 60)
        print(f"SUCCESS! Executable created at:")
        print(f"  {dist_exe}")
        print("=" * 60)
    else:
        print()
        print("BUILD FAILED. Check output above for errors.")
        sys.exit(1)
