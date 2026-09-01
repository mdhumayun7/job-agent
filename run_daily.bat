@echo off
cd /d "D:\SVNIT\SVNIT\PLACEMENT\Projects\Ongoing project\Job automation\job-agent-improved_15_may"
echo ========================================
echo   Job Agent Pro - Auto Run
echo   %date% %time%
echo ========================================
python main.py --sites naukri linkedin indeed internshala shine --retries 1
python phase2_enrichment.py
python smart_filters.py
python resume_tailor.py
python interview_prep.py
python excel_exporter.py
python report_generator.py --top 20
python history_tracker.py
echo ========================================
echo   Pipeline Complete - %time%
echo ========================================
