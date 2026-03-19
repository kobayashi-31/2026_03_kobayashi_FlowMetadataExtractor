@echo off
REM ============================================================
REM Flow Metadata Extractor - Batch Analysis Script
REM ============================================================
REM Usage:
REM   run_batch.bat                          # Run with default settings
REM   run_batch.bat --local                  # Run using local XML
REM   run_batch.bat --target-org myOrg       # Specify org
REM ============================================================

REM --- Settings ---
REM Comma-separated Flow API Names
set FLOW_NAMES=CV_UpdateTrigger,WB_UpdateTrigger,WB_UpsertFIxedBudgets,WB_DuplicatedUpdate,WB_RetryDeletion,working_budget_change_industries

REM sf CLI target org alias (empty = default org)
set TARGET_ORG=myOrg

REM Output directory
set OUTPUT_DIR=./output

REM Local XML test directory
set LOCAL_XML_DIR=./tests/fixtures

REM --- Activate Virtual Environment (if exists) ---
if exist ".venv\Scripts\activate.bat" (
    call .venv\Scripts\activate.bat
    echo [INFO] Virtual environment activated.
)

REM --- Parse Arguments ---
set USE_LOCAL=false
:parse_args
if "%~1"=="" goto :run
if "%~1"=="--local" (
    set USE_LOCAL=true
    shift
    goto :parse_args
)
if "%~1"=="--target-org" (
    set TARGET_ORG=%~2
    shift
    shift
    goto :parse_args
)
shift
goto :parse_args

:run
echo ============================================================
echo  Flow Metadata Extractor - Batch Analysis
echo ============================================================

if "%USE_LOCAL%"=="true" (
    echo [MODE] Local XML directory: %LOCAL_XML_DIR%
    python main.py --local-xml-dir %LOCAL_XML_DIR% --output-dir %OUTPUT_DIR%
) else (
    echo [MODE] Retrieve from Salesforce org: %TARGET_ORG%
    echo [FLOWS] %FLOW_NAMES%
    if "%TARGET_ORG%"=="" (
        python main.py --flow-name %FLOW_NAMES% --output-dir %OUTPUT_DIR%
    ) else (
        python main.py --flow-name %FLOW_NAMES% --output-dir %OUTPUT_DIR% --target-org %TARGET_ORG%
    )
)

echo.
echo [DONE] Output generated in: %OUTPUT_DIR%
