"""
Flow Metadata Extractor - Markdown レポート生成
FlowMetadata から人間が読みやすいレポートを生成する
"""
import logging
from pathlib import Path

from models import FlowMetadata

logger = logging.getLogger(__name__)


class MarkdownReporter:
    """FlowMetadata → 人間向け Markdown レポート"""

    def generate(self, metadata: FlowMetadata) -> str:
        """Markdown レポート文字列を生成"""
        lines = []
        self._header(lines, metadata)
        self._start_conditions(lines, metadata)
        self._execution_flow(lines, metadata)
        self._decisions(lines, metadata)
        self._record_operations(lines, metadata)
        self._apex_and_subflows(lines, metadata)
        self._dependencies(lines, metadata)
        self._unknowns_and_warnings(lines, metadata)
        return "\n".join(lines)

    def save(self, metadata: FlowMetadata, output_dir: str | Path) -> Path:
        """Markdown ファイルとして保存"""
        output_dir = Path(output_dir)
        reports_dir = output_dir / "reports"
        reports_dir.mkdir(parents=True, exist_ok=True)

        content = self.generate(metadata)
        report_path = reports_dir / "flow_report.md"
        with open(report_path, "w", encoding="utf-8") as f:
            f.write(content)
        logger.info(f"レポート保存: {report_path}")
        return report_path

    # ─── セクション生成 ───

    def _header(self, lines: list, m: FlowMetadata):
        lines.append(f"# Flow 解析レポート: {m.flow_name}")
        lines.append("")
        lines.append("## 基本情報")
        lines.append("")
        lines.append("| 項目 | 値 |")
        lines.append("|------|-----|")
        lines.append(f"| API 名 | `{m.flow_api_name}` |")
        lines.append(f"| ラベル | {m.flow_name} |")
        lines.append(f"| 説明 | {m.description or '(なし)'} |")
        lines.append(f"| 種別 | {m.process_type} |")
        lines.append(f"| トリガ | {m.trigger_type} |")
        lines.append(f"| 対象オブジェクト | {m.target_object or '(なし)'} |")
        lines.append(f"| API バージョン | {m.api_version} |")
        lines.append(f"| ステータス | {m.status} |")
        lines.append("")

    def _start_conditions(self, lines: list, m: FlowMetadata):
        lines.append("## 開始条件")
        lines.append("")

        if not m.start_conditions:
            lines.append("- 開始条件の指定なし（全レコードが対象、またはスケジュール/手動起動）")
            lines.append("")
            return

        if m.start_filter_logic:
            lines.append(f"**フィルタロジック**: `{m.start_filter_logic}`")
            lines.append("")

        for i, cond in enumerate(m.start_conditions, 1):
            if cond.get("type") == "scheduledPath":
                lines.append(f"- **スケジュールパス**: {cond.get('label', '')} "
                             f"({cond.get('offset_number', '')} {cond.get('offset_unit', '')} "
                             f"from {cond.get('time_source', '')})")
            else:
                lines.append(f"- 条件 {i}: `{cond.get('field', '')}` "
                             f"{cond.get('operator', '')} "
                             f"`{cond.get('value', '')}`")
        lines.append("")

    def _execution_flow(self, lines: list, m: FlowMetadata):
        if not m.execution_flow:
            return
        lines.append("## 処理の流れ")
        lines.append("")
        for step in m.execution_flow:
            label = step.get("label", step.get("element", ""))
            step_type = step.get("type", "")
            next_elem = step.get("next", "")
            lines.append(f"{step['order']}. **{label}** ({step_type})"
                         + (f" → {next_elem}" if next_elem else ""))
        lines.append("")

    def _decisions(self, lines: list, m: FlowMetadata):
        if not m.decisions:
            return
        lines.append("## 主要分岐")
        lines.append("")
        for dec in m.decisions:
            lines.append(f"### {dec.label} (`{dec.name}`)")
            lines.append("")
            for rule in dec.rules:
                lines.append(f"**{rule.label}** (`{rule.name}`)")
                for cond in rule.conditions:
                    lines.append(f"  - `{cond.get('left', '')}` "
                                 f"{cond.get('operator', '')} "
                                 f"`{cond.get('right', '')}`")
                if rule.connector:
                    lines.append(f"  - → `{rule.connector}`")
                lines.append("")
            if dec.default_connector:
                lines.append(f"**デフォルト** → `{dec.default_connector}`")
                lines.append("")

    def _record_operations(self, lines: list, m: FlowMetadata):
        all_ops = (
            [(op, "作成") for op in m.record_creates]
            + [(op, "更新") for op in m.record_updates]
            + [(op, "削除") for op in m.record_deletes]
            + [(op, "参照") for op in m.record_lookups]
        )
        if not all_ops:
            return

        lines.append("## レコード操作")
        lines.append("")
        lines.append("| 操作 | 名前 | オブジェクト | 項目 |")
        lines.append("|------|------|-------------|------|")
        for op, op_label in all_ops:
            fields = ", ".join(
                f"`{a.get('field', '')}`" for a in op.field_assignments
            ) if op.field_assignments else "-"
            lines.append(f"| {op_label} | {op.label} | `{op.object_name}` | {fields} |")
        lines.append("")

        # 更新フィールド一覧
        if m.updated_fields:
            lines.append("### 更新項目一覧")
            lines.append("")
            lines.append("| オブジェクト | 項目 |")
            lines.append("|-------------|------|")
            seen = set()
            for f in m.updated_fields:
                key = (f.object_name, f.field_name)
                if key not in seen:
                    seen.add(key)
                    lines.append(f"| `{f.object_name}` | `{f.field_name}` |")
            lines.append("")

    def _apex_and_subflows(self, lines: list, m: FlowMetadata):
        if not m.apex_actions and not m.subflows and not m.action_calls:
            return

        lines.append("## 呼び出し先")
        lines.append("")
        lines.append("| 種別 | 名前 | 詳細 |")
        lines.append("|------|------|------|")
        for a in m.apex_actions:
            lines.append(f"| Apex | `{a.apex_class}` | {a.label} |")
        for s in m.subflows:
            lines.append(f"| Subflow | `{s.flow_name}` | {s.label} |")
        for ac in m.action_calls:
            lines.append(f"| {ac.action_type} | `{ac.action_name}` | {ac.label} |")
        lines.append("")

    def _dependencies(self, lines: list, m: FlowMetadata):
        if not m.dependencies:
            return
        lines.append("## 依存関係一覧")
        lines.append("")
        lines.append("| タイプ | 名前 | 用途 |")
        lines.append("|--------|------|------|")
        for d in m.dependencies:
            lines.append(f"| {d.dep_type} | `{d.name}` | {d.context} |")
        lines.append("")

    def _unknowns_and_warnings(self, lines: list, m: FlowMetadata):
        if m.unknowns:
            lines.append("## ⚠ 不明点")
            lines.append("")
            for u in m.unknowns:
                lines.append(f"- **{u.element}**: {u.description}")
                if u.suggestion:
                    lines.append(f"  - 💡 {u.suggestion}")
            lines.append("")

        if m.warnings:
            lines.append("## 🔶 保守リスク・注意点")
            lines.append("")
            for w in m.warnings:
                severity_icon = {"high": "🔴", "medium": "🟡", "low": "🟢"}.get(w.severity, "🟡")
                lines.append(f"- {severity_icon} [{w.warning_type}] {w.description}")
            lines.append("")

        # 確認すべき周辺自動化（定型出力）
        lines.append("## 📋 確認すべき周辺自動化")
        lines.append("")
        if m.target_object:
            lines.append(f"- `{m.target_object}` に対する他の Flow")
            lines.append(f"- `{m.target_object}` の ValidationRule")
            lines.append(f"- `{m.target_object}` に対する Process Builder / Workflow Rule（レガシー）")
            lines.append(f"- `{m.target_object}` のトリガ（Apex Trigger）")
        else:
            lines.append("- 対象オブジェクトが特定できないため、手動確認が必要です")
        lines.append("")
