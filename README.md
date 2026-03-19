# Flow Metadata Extractor

Salesforce Flow のメタデータ XML を解析し、依存関係の抽出・AI 向けJSON・人間向け Markdown レポートを生成するツールです。

## セットアップ

```bash
# Python 3.10+ が必要（外部ライブラリ不要）
python --version

# sf CLI（Salesforce org から retrieve する場合）
sf --version
```

## 使い方

### Salesforce org から取得して解析

```bash
python main.py --flow-name MyFlowApiName --target-org myOrgAlias
```

### ローカル XML を直接解析（テスト・オフライン）

```bash
python main.py --local-xml ./path/to/MyFlow.flow-meta.xml
```

### オプション

| オプション | 説明 | デフォルト |
|-----------|------|-----------|
| `--flow-name` | 対象 Flow の API Name | - |
| `--local-xml` | ローカル XML ファイルパス | - |
| `--target-org` | sf CLI の接続先 org エイリアス | デフォルト org |
| `--output-dir` | 出力先ディレクトリ | `./output` |
| `--no-resolve-deps` | 依存先の追加 retrieve をスキップ | false |
| `--no-report` | Markdown レポート生成をスキップ | false |
| `--verbose` | 詳細ログを出力 | false |

## 出力ファイル

```
output/
├── analysis/
│   ├── flow_analysis.json    # AI 解析用 中間 JSON
│   └── dependencies.json     # 依存関係一覧
├── reports/
│   └── flow_report.md        # 人間向け Markdown レポート
├── raw/                      # retrieve した生メタデータ
└── flow_analyzer.log         # 実行ログ
```

## モジュール構成

| ファイル | 責務 |
|---------|------|
| `main.py` | CLI エントリーポイント |
| `models.py` | データクラス定義 |
| `retriever.py` | sf CLI メタデータ取得 |
| `parser.py` | Flow XML 解析・依存抽出 |
| `dependency_resolver.py` | 依存先の追加 retrieve |
| `normalizer.py` | AI 向け JSON 生成 |
| `reporter.py` | Markdown レポート生成 |

## 解析される要素

- 開始条件（トリガ、フィルタ）
- 分岐条件（Decision）
- レコード操作（作成/更新/削除/参照）
- Apex アクション呼び出し
- サブフロー呼び出し
- 数式（内部フィールド参照の抽出）
- 依存オブジェクト・フィールドの一覧
- 実行フロー（connector 追跡）
- 保守リスク・不明点の自動検出
