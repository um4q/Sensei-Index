@echo off
REM Double-click to export every Valve Log row marked "Y" in column A.
REM Filled PDFs will appear in the output_pdfs folder next to this file.

cd /d "%~dp0"
python export_valve_to_pdf.py "Equipment_Inspection_Tracker.xlsx"
echo.
echo ============================================================
echo Done. Check the output_pdfs folder for your filled PDF(s).
echo ============================================================
pause
