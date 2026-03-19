@echo off
REM ============================================================
REM Flow Metadata Extractor - 複数 Flow 一括解析スクリプト
REM ============================================================
REM 使い方:
REM   run_batch.bat                          # デフォルト設定で実行
REM   run_batch.bat --local                  # ローカル XML で実行
REM   run_batch.bat --target-org myOrg       # org を指定
REM ============================================================

REM ─── 設定 ───
REM カンマ区切りで対象 Flow の API Name を列挙
set FLOW_NAMES=CV_UpdateTrigger,WB_UpdateTrigger,WB_UpsertFIxedBudgets,WB_DuplicatedUpdate,WB_RetryDeletion,working_budget_change_industries

REM sf CLI の接続先 org エイリアス（空ならデフォルト org）
set TARGET_ORG=myOrg

REM 出力先
set OUTPUT_DIR=./output

REM ローカル XML テスト用ディレクトリ
set LOCAL_XML_DIR=./tests/fixtures

REM ─── 仮想環境の有効化 ───
if exist ".venv\Scripts\activate.bat" (
    call .venv\Scripts\activate.bat
    echo [INFO] 仮想環境を有効化しました
)

REM ─── 引数チェック ───
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
echo  Flow Metadata Extractor - 一括解析
echo ============================================================

if "%USE_LOCAL%"=="true" (
    echo [MODE] ローカル XML ディレクトリ: %LOCAL_XML_DIR%
    python main.py --local-xml-dir %LOCAL_XML_DIR% --output-dir %OUTPUT_DIR%
) else (
    echo [MODE] Salesforce org から retrieve
    echo [FLOWS] %FLOW_NAMES%
    if "%TARGET_ORG%"=="" (
        python main.py --flow-name %FLOW_NAMES% --output-dir %OUTPUT_DIR%
    ) else (
        echo [ORG] %TARGET_ORG%
        python main.py --flow-name %FLOW_NAMES% --output-dir %OUTPUT_DIR% --target-org %TARGET_ORG%
    )
)

echo.
echo [DONE] 出力先: %OUTPUT_DIR%
