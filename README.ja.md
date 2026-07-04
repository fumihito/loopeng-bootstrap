# Loop Engineering Bootstrap

Loop Engineering Bootstrap は、AI エージェントの作業を engineered loop として運用するための bootstrap kit です。LLM role の外側に deterministic な制御層を置き、人間が最終権限を持ちます。提供する入口は 2 層で、`direct:` / `route:` / `frame-*` による bounded なルーティングと、その上に載る contract-gated な自律ループです。

## Core concept

Turn contract は Loop Brief から始まり、Gatekeeper が依頼の正当性・境界・明示性を確認して loop 開始可否を決めます。
Sensemaker が問題をフレーミングし、State Steward・Meta-Evaluator・関連 role が state、learning、memory を生成系から分離します。
deterministic hooks は protected path、command boundary、skill loading、sanitized telemetry を強制します。
各 cycle は budget と stop condition に束縛されます。
次の cycle は model の自己改変ではなく、handoff state と scheduler から来ます。
全体像は `docs/loop-structure.svg` と `docs/ARCHITECTURE.md` を参照してください。

## Install

full install の前提は Go 1.21+ です。
routing profile は Go で実装された loop layer を必要としません。

```bash
python3 install.py --repo /path/to/repository
python3 install.py --repo /path/to/repository --profile routing
python3 install.py --repo .
```

mixed な Codex / Claude layout、semantic merge workflow、LLM assisted install の詳細は `docs/INSTALL.md` にあります。

## First contact

prefix なしで始めると Gatekeeper intake に入ります。Gatekeeper と `loop-brief-assistant` が contract 作成を支援します。
`route:` は `frame-*` 候補を提案する pre-loop 入口です。
`direct:` は autonomous loop を通さない bounded な single-turn です。

```text
repair CI failures under this operating contract ...
```

詳細は `docs/GATEKEEPER_PROTOCOL.md` と `docs/COMMAND_ROUTING.md` を参照してください。

## Documentation map

| Doc | 内容 |
|---|---|
| `docs/ARCHITECTURE.md` | role 分割の理由と却下した代替案。 |
| `docs/COMMAND_ROUTING.md` | `route:` の提案フローと `frame-*` 選択規則。 |
| `docs/DIRECT_MODE.md` | bounded な read-only `direct:` turn。 |
| `docs/SOP_ROUTING.md` | mandatory な `<header>:` の SOP ルーティング。 |
| `docs/GATEKEEPER_PROTOCOL.md` | Gatekeeper intake、contract 項目、verdict。 |
| `docs/LOOP_INPUT_GUIDE.md` | autonomous loop に必要な人間入力。 |
| `docs/OKF_LLMWIKI.md` | OKF LLMWiki の durable memory ルール。 |
| `docs/LEARNING_OBSERVABILITY.md` | cross-turn learning 指標と audit flow。 |
| `docs/OBSERVABILITY.md` | deterministic な loop-status と learning-health 表示。 |
| `docs/SCHEDULER.md` | scheduler daemon、cadence、handoff。 |
| `docs/TELEMETRY.md` | sanitized OTel schema と collector 挙動。 |
| `docs/INSTALL.md` | full install、routing profile、mixed layout、semantic merge。 |
| `docs/RELEASE_AUDIT.md` | completion protocol、audit guard、release checks。 |

## Status

Active development です。loop contract、install flow、routing behavior は今後も変わり得ます。
ライセンスは MIT License です。
