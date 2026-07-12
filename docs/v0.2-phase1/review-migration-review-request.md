# `review:` migration review request

Hito にレビューを依頼する。`docs/v0.2-phase1/` の現行文書を走査したが、明示的な「未決事項」または同義の未解決項目は確認できなかったため、未決の decision を推測して OKF に登録することはしなかった。

起案した [review-migration-report.json](review-migration-report.json) は、通常の OKF apply 規律でレビュー後に適用できる空の report である。追加の未決事項が見つかった場合は、`decisions/` 文書に `pending-decision` タグと `# Invalidation` 節を付けてこの report に追加する。
