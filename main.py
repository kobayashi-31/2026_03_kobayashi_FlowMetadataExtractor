"""
Flow Metadata Extractor - CLI エントリーポイント
Salesforce Flow のメタデータを取得・解析し、JSON/Markdown を出力する

使い方:
  # 単一 Flow
  python main.py --flow-name MyFlow --target-org myOrg

  # 複数 Flow（カンマ区切り）
  python main.py --flow-name Flow1,Flow2,Flow3 --target-org myOrg

  # ローカル XML を直接解析
  python main.py --local-xml ./path/to/MyFlow.flow-meta.xml

  # ディレクトリ内の全 Flow XML を一括解析
  python main.py --local-xml-dir ./path/to/flows/

  # 依存先の追加 retrieve をスキップ
  python main.py --flow-name MyFlow --no-resolve-deps
"""
import argparse
import logging
import sys
from pathlib import Path

from retriever import MetadataRetriever
from parser import FlowParser
from dependency_resolver import DependencyResolver
from normalizer import AnalysisNormalizer
from reporter import MarkdownReporter


def setup_logging(output_dir: Path, verbose: bool = False):
    """ログ設定"""
    log_level = logging.DEBUG if verbose else logging.INFO
    log_dir = output_dir
    log_dir.mkdir(parents=True, exist_ok=True)

    logging.basicConfig(
        level=log_level,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        handlers=[
            logging.StreamHandler(sys.stdout),
            logging.FileHandler(
                log_dir / "flow_analyzer.log", encoding="utf-8"
            ),
        ],
    )


def parse_args():
    """CLI 引数を解析"""
    p = argparse.ArgumentParser(
        description=(
            "Salesforce Flow Metadata Extractor"
            " - Flow の解析と依存関係の可視化"
        )
    )
    # 入力（いずれか必須）
    group = p.add_mutually_exclusive_group(required=True)
    group.add_argument(
        "--flow-name",
        help="対象 Flow の API Name（カンマ区切りで複数指定可）"
    )
    group.add_argument(
        "--local-xml",
        help="ローカルの Flow XML ファイルパス"
    )
    group.add_argument(
        "--local-xml-dir",
        help="Flow XML が入ったディレクトリ（一括解析）"
    )

    # オプション
    p.add_argument(
        "--target-org", default="",
        help="sf CLI の接続先 org エイリアス"
    )
    p.add_argument(
        "--output-dir", default="./output",
        help="出力先ディレクトリ (default: ./output)"
    )
    p.add_argument(
        "--no-resolve-deps", action="store_true",
        help="依存先の追加 retrieve をスキップ"
    )
    p.add_argument(
        "--no-report", action="store_true",
        help="Markdown レポート生成をスキップ"
    )
    p.add_argument(
        "--verbose", action="store_true",
        help="詳細ログを出力"
    )

    return p.parse_args()


def analyze_single_flow(
    xml_path: Path,
    output_dir: Path,
    retriever: MetadataRetriever,
    resolve_deps: bool,
    generate_report: bool,
    logger: logging.Logger,
):
    """単一 Flow を解析して出力"""
    flow_api_name = xml_path.stem.replace(".flow-meta", "")
    logger.info(f"── {flow_api_name} の解析開始 ──")

    # 解析
    parser = FlowParser()
    metadata = parser.parse(xml_path)
    logger.info(
        f"解析完了: {metadata.flow_name} ({metadata.process_type})"
    )

    # 依存先の追加 retrieve
    if resolve_deps:
        resolver = DependencyResolver(retriever)
        dep_results = resolver.resolve(metadata)
        ok_count = sum(
            1 for v in dep_results.values() if v.get("retrieved")
        )
        logger.info(f"追加 retrieve: {ok_count} 件成功")

    # JSON 出力
    normalizer = AnalysisNormalizer()
    analysis_path, deps_path = normalizer.save(
        metadata, output_dir
    )
    logger.info(f"JSON: {analysis_path}")

    # Markdown レポート
    report_path = None
    if generate_report:
        reporter = MarkdownReporter()
        report_path = reporter.save(metadata, output_dir)
        logger.info(f"レポート: {report_path}")

    return metadata


def generate_batch_summary(
    all_metadata: list,
    output_dir: Path,
    logger: logging.Logger,
):
    """複数 Flow の一括サマリレポートを生成"""
    lines = []
    lines.append("# Flow 一括解析サマリ")
    lines.append("")
    lines.append(f"解析フロー数: **{len(all_metadata)}**")
    lines.append("")

    # 一覧テーブル
    lines.append("## フロー一覧")
    lines.append("")
    lines.append(
        "| # | API 名 | ラベル | 種別 | トリガ |"
        " 対象オブジェクト | 依存先数 |"
    )
    lines.append(
        "|---|--------|--------|------|--------|"
        "----------------|----------|"
    )
    for i, m in enumerate(all_metadata, 1):
        lines.append(
            f"| {i} | `{m.flow_api_name}` | {m.flow_name}"
            f" | {m.process_type} | {m.trigger_type}"
            f" | {m.target_object or '-'}"
            f" | {len(m.dependencies)} |"
        )
    lines.append("")

    # 依存オブジェクト横断
    all_objects = set()
    all_apex = set()
    all_subflows = set()
    for m in all_metadata:
        for d in m.dependencies:
            if d.dep_type == "CustomObject":
                all_objects.add(d.name)
            elif d.dep_type == "ApexClass":
                all_apex.add(d.name)
            elif d.dep_type == "Flow":
                all_subflows.add(d.name)

    lines.append("## 共通依存先")
    lines.append("")

    if all_objects:
        lines.append("### オブジェクト")
        lines.append("")
        for obj in sorted(all_objects):
            # このオブジェクトを使っている Flow を列挙
            users = [
                m.flow_api_name for m in all_metadata
                if any(
                    d.name == obj and d.dep_type == "CustomObject"
                    for d in m.dependencies
                )
            ]
            lines.append(
                f"- `{obj}` ← {', '.join(f'`{u}`' for u in users)}"
            )
        lines.append("")

    if all_apex:
        lines.append("### Apex クラス")
        lines.append("")
        for cls in sorted(all_apex):
            users = [
                m.flow_api_name for m in all_metadata
                if any(
                    d.name == cls and d.dep_type == "ApexClass"
                    for d in m.dependencies
                )
            ]
            lines.append(
                f"- `{cls}` ← {', '.join(f'`{u}`' for u in users)}"
            )
        lines.append("")

    if all_subflows:
        lines.append("### サブフロー")
        lines.append("")
        for sf in sorted(all_subflows):
            users = [
                m.flow_api_name for m in all_metadata
                if any(
                    d.name == sf and d.dep_type == "Flow"
                    for d in m.dependencies
                )
            ]
            lines.append(
                f"- `{sf}` ← {', '.join(f'`{u}`' for u in users)}"
            )
        lines.append("")

    # 更新フィールド横断
    all_updates = {}
    for m in all_metadata:
        for f in m.updated_fields:
            key = f"{f.object_name}.{f.field_name}"
            if key not in all_updates:
                all_updates[key] = []
            if m.flow_api_name not in all_updates[key]:
                all_updates[key].append(m.flow_api_name)

    if all_updates:
        lines.append("## 更新フィールド横断一覧")
        lines.append("")
        lines.append("| フィールド | 更新元 Flow |")
        lines.append("|-----------|------------|")
        for field_key in sorted(all_updates.keys()):
            flows = all_updates[field_key]
            lines.append(
                f"| `{field_key}`"
                f" | {', '.join(f'`{f}`' for f in flows)} |"
            )
        lines.append("")

    # ⚠ 同一フィールドを複数 Flow で更新している場合の警告
    conflicts = {
        k: v for k, v in all_updates.items() if len(v) > 1
    }
    if conflicts:
        lines.append("## ⚠ 競合リスク")
        lines.append("")
        lines.append(
            "以下のフィールドは複数の Flow から更新されています。"
            "実行順序やトリガ条件を確認してください。"
        )
        lines.append("")
        for field_key, flows in conflicts.items():
            lines.append(
                f"- **`{field_key}`**"
                f" ← {', '.join(f'`{f}`' for f in flows)}"
            )
        lines.append("")

    # 書き出し
    report_dir = output_dir / "reports"
    report_dir.mkdir(parents=True, exist_ok=True)
    summary_path = report_dir / "batch_summary.md"
    with open(summary_path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))
    logger.info(f"一括サマリ: {summary_path}")

    return summary_path


def main():
    args = parse_args()
    output_dir = Path(args.output_dir)

    # ログ設定
    setup_logging(output_dir, args.verbose)
    logger = logging.getLogger(__name__)
    logger.info("=" * 60)
    logger.info("Flow Metadata Extractor 開始")
    logger.info("=" * 60)

    retriever = MetadataRetriever(
        target_org=args.target_org,
        output_dir=str(output_dir),
    )

    # ── XML パスのリストを構築 ──
    xml_paths = []
    is_local = bool(args.local_xml or args.local_xml_dir)

    if args.local_xml:
        # 単一ローカルファイル
        p = Path(args.local_xml)
        if p.exists():
            xml_paths.append(p)
        else:
            logger.error(f"ファイルが見つかりません: {p}")
            sys.exit(1)

    elif args.local_xml_dir:
        # ディレクトリ内の全 .flow-meta.xml を収集
        d = Path(args.local_xml_dir)
        if not d.is_dir():
            logger.error(f"ディレクトリが見つかりません: {d}")
            sys.exit(1)
        xml_paths = sorted(d.glob("*.flow-meta.xml"))
        if not xml_paths:
            # サブディレクトリも探す
            xml_paths = sorted(d.rglob("*.flow-meta.xml"))
        if not xml_paths:
            logger.error(f"Flow XML が見つかりません: {d}")
            sys.exit(1)
        logger.info(f"{len(xml_paths)} 件の Flow XML を検出")

    else:
        # sf CLI で retrieve
        if not retriever.check_sf_cli():
            logger.error("sf CLI が利用できません。終了します。")
            sys.exit(1)

        flow_names = [
            n.strip() for n in args.flow_name.split(",")
            if n.strip()
        ]
        for name in flow_names:
            result = retriever.retrieve_flow(name)
            if result is None:
                logger.error(
                    f"Flow '{name}' の retrieve に失敗しました。"
                    " スキップします。"
                )
                continue
            found = retriever.find_flow_xml(name)
            if found:
                xml_paths.append(found)
            else:
                logger.error(f"Flow XML が見つかりません: {name}")

    if not xml_paths:
        logger.error("解析対象の Flow XML がありません。終了します。")
        sys.exit(1)

    # ── 各 Flow を解析 ──
    is_batch = len(xml_paths) > 1
    all_metadata = []
    resolve = not args.no_resolve_deps and not is_local
    gen_report = not args.no_report

    for xml_path in xml_paths:
        flow_api_name = xml_path.stem.replace(".flow-meta", "")
        # 複数 Flow の場合は Flow ごとにサブディレクトリ
        if is_batch:
            flow_output = output_dir / flow_api_name
        else:
            flow_output = output_dir

        metadata = analyze_single_flow(
            xml_path=xml_path,
            output_dir=flow_output,
            retriever=retriever,
            resolve_deps=resolve,
            generate_report=gen_report,
            logger=logger,
        )
        all_metadata.append(metadata)

    # ── 一括サマリ（複数 Flow の場合のみ） ──
    if is_batch:
        generate_batch_summary(all_metadata, output_dir, logger)

    # ── 完了 ──
    logger.info("=" * 60)
    logger.info(
        f"Flow Metadata Extractor 完了"
        f" ({len(all_metadata)} Flow 解析)"
    )
    logger.info(f"出力先: {output_dir.resolve()}")
    logger.info("=" * 60)


if __name__ == "__main__":
    main()
