# Loop Engineering Bootstrap

Loop Engineering Bootstrap は、AI コーディングエージェント(Codex / Claude Code 両用)の自走を「監査可能なループ」として運用するための bootstrap kit です。v0.2 系は Python のみで実装され(0.1では Golang を用いていましたが破棄)、事前の抑止を最小限に絞り、代わりに全ランの結果を決定論的な Run Report とアラートで可視化します。耐久メモリは OKF 形式の LLMWiki への検証済みトランザクションとしてのみ更新されます。

このリポジトリそのものに Bootstrap が自己適用されています。

## Core concept

v0.2 は 4 つの柱で構成されます。

1. **自走可能性** — エージェントは人間の逐次承認なしにランを実行できます。次のターンの入力は、前のランが書き出した handoff と Run Report から決定論的に構成され、モデルの自己申告記憶を持ち越しません。
2. **監査性** — 各ランの操作は journal(append-only・sanitize 済み)に記録され、`audit run` が固定順の検査を実行して Run Report を生成します。完了宣言は Run Report の生成をもってのみ行われます。
3. **alert-not-block** — 事前に抑止するのは限定列挙された hard block(破壊的コマンド、秘密情報の永続化、不正なメモリ適用、リポジトリ外書き込み)のみです。それ以外の逸脱は作業を止めず、Run Report にアラートとして記録されます。protected path の変更は、ラン内で intent を事前宣言していれば warn、未宣言なら critical になります。
4. **OKF LLMWiki メモリ** — 耐久メモリの書き込みは、スキーマ検証・名前空間封じ込め・proposal_id・操作数と文書サイズの上限を通過した `okf apply` トランザクションのみです。削除は行わず、`DEPRECATE` による status 反転で履歴を保持します。

## Components

| 対象 | 内容 |
|---|---|
| `loopeng/` | 制御層の Python パッケージ(stdlib のみ)。CLI は `python3 -m loopeng <subcommand>` |
| `loopeng okf` | `init` / `validate` / `apply` / `reindex` / `log` / `query` / `draft` — LLMWiki の初期化・検索・起案・更新 |
| `loopeng learning promote` | learning backlog から検証済み draft を生成(適用はしない) |
| `loopeng memory curate` | 自律名前空間の provisional UPSERT を最大3件まで適用 |
| `loopeng memory stats` | LLMWiki の変異窓とバンドル外コミットを集計 |
| `loopeng journal add` | ランへのイベント追記(`run-start` / `intent` / `mutation` / `run-end` など) |
| `loopeng audit run` | 検査の実行、Run Report 生成、handoff 書き出し |
| `loopeng schedule next` | 前ランの handoff から次ターンの前文を生成 |
| `loopeng status` | 直近 Run Report と learning backlog の要約 |
| `loopeng review` | 直近ランの結果・懸念・前提をレビュー。`--triage` で誘導し、`dag` で Mermaid/SVG のループ図を生成 |
| `loopeng hook` | Claude Code / Codex の hook 入口。journal 自動取得と hard block の事前執行を担う |
| `./loopeng.py` | `python3 -m loopeng` と同等の短縮ランチャ |
| `skills/frame-*` | 思考フレーム skill 群(唯一の配布 skill。編集点は `adapters/shared/skills/`) |
| `utils/phase1_gate.py` / `utils/phase1_gate_ext.py` | 実行可能な受け入れゲート(変更禁止。完了判定の唯一の根拠) |
| `utils/audit_guard.py` | このリポジトリ自体の completion protocol(pre-push 監査) |

## Install

`LANG` でヘルプ言語を選べます。未設定または `ja` で始まる場合は日本語、それ以外は英語です。

Python 3.10+ を前提とします。

```bash
# frame-* skill のみ(routing プロファイル)
python3 install.py --repo /path/to/repository --profile routing

# skill + loopeng 制御層 + state 雛形(full プロファイル)
python3 install.py --repo /path/to/repository --profile full

# 既存環境の更新。v0.1 の導入痕跡(旧フック・旧ポリシー)を検出した場合は
# 退避アーカイブへ移して v0.2 へ収束させます(削除はしません)
python3 install.py --repo /path/to/repository --profile full --update
```

v0.1 を導入していた環境では、`.loop-engineering-backups/<timestamp>/` に待避されます。移行の内容は `.agent-loop/state/reports/` の移行レポートに記録されます。詳細は `docs/INSTALL.md` を参照してください。

## Run cycle

```bash
cd /path/to/repository
# `./loopeng.py` は `python3 -m loopeng` と同等の短縮起動です。
python3 -m loopeng okf init llmwiki        # 初回のみ

RUN_ID=$(date +%Y%m%d-%H%M%S)
python3 -m loopeng journal add --run "$RUN_ID" \
  --event '{"kind":"run-start","agent":"codex","goal":"..."}'
# ... エージェント作業。protected path に触れる前に intent を宣言し、
#     各ステップを journal に追記する ...
python3 -m loopeng okf apply memory-report.json --bundle llmwiki   # メモリ更新がある場合
python3 -m loopeng journal add --run "$RUN_ID" --event '{"kind":"run-end"}'
python3 -m loopeng audit run --run "$RUN_ID"   # Run Report + handoff を生成
python3 -m loopeng schedule next               # 次ターンの前文
```

Run Report に critical アラート(未宣言の protected path 変更、journal 未記録の変異など)がある場合、冒頭に人間レビュー要のバナーが付きます。バナーは作業を遡って無効化しませんが、完了の受け入れはレビュー後に判断してください。

## Documentation map

| Doc | 内容 |
|---|---|
| `docs/ARCHITECTURE.md` | v0.2 の構成と統制方針(hard block の執行点を含む)。 |
| `docs/RUN_REPORT.md` | Run Report のスキーマと journal イベント規約。 |
| `docs/OKF_LLMWIKI.md` | OKF LLMWiki の耐久メモリ規則とトランザクション。 |
| `docs/INSTALL.md` | プロファイル、更新、v0.1 からの収束移行。 |
| `docs/LOOP_INPUT_GUIDE.md` | 自走ランに必要な人間側の入力。 |
| `docs/RELEASE_AUDIT.md` | completion protocol と pre-push audit guard。 |
| `docs/DESIGN_PHILOSOPHY.md` | 設計原則(単一宣言点、機構優先など)。 |
| `docs/v0.2-phase1/` | v0.2 再設計の実装指示・監査記録(履歴資料)。 |

## Development

このリポジトリ自体の開発は次の規律に従います: 変更は journal 化されたランとして実施し、完了は Run Report で宣言します。リリース対象の変更は `utils/audit_guard.py record` による監査記録を経てから push します。受け入れゲート(`utils/phase1_gate.py` / `utils/phase1_gate_ext.py`)は GREEN を維持しなければならず、ゲート自体の変更は禁止です。

## Status

v0.2 系(active development)。バージョンは v15 系(v0.1 設計)から再出発しており、v0.1 と互換しません。v0.1 の統治機構(Gatekeeper / Sensemaker / Loop Brief、`route:` / `brief:` / `direct:` 入口、Go 実装、OTel/systemd 常駐)は退役し、`--update` による収束移行で置き換えられます。このリリースでは、共通 hooks、`review:`/`review dag`、audit record のコミット吸収を実装済みです。進行中の拡張:

<!-- ongoing-start -->
none
<!-- ongoing-end -->

耐久メモリ参照は `index.md → okf query → 上位 K 件(既定 5)の本文読み込み` の順とし、`llmwiki/` の一括読み込みは行いません。
provisional エントリは観測記録として扱い、行動の制約・決定の根拠としては established を優先します。自律名前空間の provisional UPSERT は `memory curate` が適用し、それ以外の `memory-drafts` 適用は当該ランでユーザーが明示指示した場合のみ行います。

ライセンスは MIT License です。
