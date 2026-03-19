"""
Flow Metadata Extractor - AI 向け正規化 JSON 生成
FlowMetadata を AI 解析用の中間 JSON に変換する
"""
import json
import logging
from datetime import datetime, timezone
from dataclasses import asdict
from pathlib import Path

from models import FlowMetadata

logger = logging.getLogger(__name__)

TOOL_VERSION = "1.0.0"


class AnalysisNormalizer:
    """FlowMetadata を AI 解析向け JSON に変換"""

    def normalize(self, metadata: FlowMetadata) -> dict:
        """FlowMetadata → AI 向け辞書"""
        return {
            "meta": {
                "tool_version": TOOL_VERSION,
                "generated_at": datetime.now(timezone.utc).isoformat(),
                "flow_api_name": metadata.flow_api_name,
            },
            "facts": {
                "flow_name": metadata.flow_name,
                "flow_api_name": metadata.flow_api_name,
                "description": metadata.description,
                "process_type": metadata.process_type,
                "trigger_type": metadata.trigger_type,
                "target_object": metadata.target_object,
                "api_version": metadata.api_version,
                "status": metadata.status,
                "start_conditions": {
                    "filter_logic": metadata.start_filter_logic,
                    "filters": metadata.start_conditions,
                },
                "elements": {
                    "decisions": [asdict(d) for d in metadata.decisions],
                    "formulas": [asdict(f) for f in metadata.formulas],
                    "record_creates": [asdict(r) for r in metadata.record_creates],
                    "record_updates": [asdict(r) for r in metadata.record_updates],
                    "record_deletes": [asdict(r) for r in metadata.record_deletes],
                    "record_lookups": [asdict(r) for r in metadata.record_lookups],
                    "apex_actions": [asdict(a) for a in metadata.apex_actions],
                    "subflows": [asdict(s) for s in metadata.subflows],
                    "action_calls": [asdict(a) for a in metadata.action_calls],
                    "assignments": metadata.assignments,
                    "loops": metadata.loops,
                },
                "dependencies": {
                    "objects": list({d.name for d in metadata.dependencies if d.dep_type == "CustomObject"}),
                    "apex_classes": list({d.name for d in metadata.dependencies if d.dep_type == "ApexClass"}),
                    "subflows": list({d.name for d in metadata.dependencies if d.dep_type == "Flow"}),
                    "referenced_fields": [asdict(f) for f in metadata.referenced_fields],
                    "updated_fields": [asdict(f) for f in metadata.updated_fields],
                },
                "execution_flow": metadata.execution_flow,
            },
            "inferences": {
                "business_purpose_hypothesis": "",
                "maintenance_risks": [],
                "notes": [],
            },
            "unknowns": [asdict(u) for u in metadata.unknowns],
            "warnings": [asdict(w) for w in metadata.warnings],
        }

    def save(self, metadata: FlowMetadata, output_dir: str | Path):
        """JSON ファイルとして保存"""
        output_dir = Path(output_dir)
        analysis_dir = output_dir / "analysis"
        analysis_dir.mkdir(parents=True, exist_ok=True)

        # メイン解析 JSON
        analysis_data = self.normalize(metadata)
        analysis_path = analysis_dir / "flow_analysis.json"
        with open(analysis_path, "w", encoding="utf-8") as f:
            json.dump(analysis_data, f, ensure_ascii=False, indent=2)
        logger.info(f"AI 解析用 JSON 保存: {analysis_path}")

        # 依存関係一覧 JSON
        deps_data = {
            "flow_api_name": metadata.flow_api_name,
            "dependencies": [asdict(d) for d in metadata.dependencies],
        }
        deps_path = analysis_dir / "dependencies.json"
        with open(deps_path, "w", encoding="utf-8") as f:
            json.dump(deps_data, f, ensure_ascii=False, indent=2)
        logger.info(f"依存関係 JSON 保存: {deps_path}")

        return analysis_path, deps_path
