# MCP 활용 가이드 (M3 인계용 stub)

이 문서는 **Claude Code(또는 다른 MCP 클라이언트)가 GAH MCP 서버를 어떻게 사용하면 좋은지** 알려 주는 가이드의 시작점이다. M2 시점에는 MCP 서버 자체가 아직 없으므로, 본 문서는 M3 가 MCP 도구를 구현할 때 그대로 코드로 옮길 **인터페이스 계약**과 **권장 사용 흐름**을 미리 박아 둔다.

본문은 M3 끝에서 실제 응답 JSON 예시로 풀어쓴다. 현재는 골격만 둔다.

## 1. 라벨 어휘는 "자기 기술" 한다

GAH 의 라벨 어휘는 24축 ≈ 316개의 영어 enum 토큰으로 구성된다. 각 라벨은 영어 한 줄 description 을 동봉하므로, Claude Code 는 사용자 자연어 쿼리를 **라벨 어휘에 매핑**할 수 있다.

M3 가 추가할 메타 도구:

- `list_label_axes() -> { axes: ["category", "style", ..., "sound_voice_type"] }`
- `list_labels(axis, enabled_only=true, with_description=true) -> { labels: [...], signature: "..." }`
- `describe_label(axis, label) -> { axis, label, description, sample_assets: [...] }`

권장 흐름:
1. **세션 시작 시** `list_labels(with_description=true)` 한 번 호출 → 응답의 `signature` 와 함께 캐시.
2. 이후 호출에서 `signature` 가 동일하면 캐시 재사용. 사용자가 GUI 라벨 관리에서 라벨을 추가/비활/편집하면 signature 가 바뀌므로 다음 호출에서 자동 새로고침.

## 2. 자연어 쿼리는 그대로 + 라벨 부울 필터 권장

사용자가 `"전투 시 깔릴 빠르고 어두운 오케스트라 BGM, 1분 이내, 루프"` 같은 자연어로 요청하면 Claude Code 는:

1. 자연어 쿼리를 그대로 `find_asset` 에 `query` 로 전달.
2. 동시에 라벨 어휘를 활용해 **부울 필터**를 같이 보낸다:

   ```jsonc
   {
     "query": "전투 시 깔릴 빠르고 어두운 오케스트라 BGM",
     "kind": "sound",
     "filters": { "max_duration_ms": 60000, "loopable": true },
     "labels_all": [{"axis": "sound_category", "label": "bgm"}],
     "labels_any": [
       {"axis": "sound_mood",       "label": "dark"},
       {"axis": "sound_use",        "label": "combat"},
       {"axis": "sound_tempo",      "label": "fast"},
       {"axis": "sound_genre",      "label": "orchestral"},
       {"axis": "sound_instrument", "label": "strings"}
     ],
     "project_id": "D:/Unity/MyGame",
     "count": 5
   }
   ```

3. 서버는 임베딩 코사인 + FTS5 BM25 + `asset_labels.score` + 통일성 가중치를 합산해 top-N 을 돌려준다.

## 3. 응답의 `matched_labels` 가 추천 근거다

응답에는 각 결과의 매칭된 라벨이 들어온다:

```jsonc
{
  "asset_id": 142,
  "score": 0.91,
  "matched_labels": [
    {"axis": "sound_category", "label": "bgm",        "source": "gemma", "score": 0.85},
    {"axis": "sound_mood",     "label": "dark",       "source": "gemma", "score": 0.78},
    {"axis": "sound_tempo",    "label": "fast",       "source": "gemma", "score": 0.78},
    {"axis": "sound_genre",    "label": "orchestral", "source": "gemma", "score": 0.78},
    {"axis": "sound_use",      "label": "combat",     "source": "gemma", "score": 0.78}
  ],
  "score_breakdown": {
    "semantic": 0.42, "keyword": 0.15,
    "label_match": 0.20, "consistency": 0.14
  },
  "why": "…",
  "path": "C:/.../battle_dark_01.ogg"
}
```

Claude Code 는 이 정보를 사용자에게 그대로 풀어쓸 수 있어 **추천 근거가 자동 생성**된다.

## 4. 표준 워크플로 (DESIGN §13 참조)

세션 흐름:

1. `list_packs` + `list_labels(with_description=true)` → 카탈로그/어휘 캐시.
2. 사용자 요청 → `suggest_packs(query, project_id, kind)` → 사용자에게 팩 후보 제시.
3. 사용자가 팩 선택 → `find_asset(force_pack_id=<선택>, ...)`.
4. Unity 프로젝트로 복사 후 → `record_asset_use(asset_id, project_id, query_id)`.

`project_id` 는 매 호출에 그대로 전달. 통일성 가중치가 이력 기반으로 같은 프로젝트를 같은 팩 쪽으로 수렴시킨다.

## 5. M3 작업 시 참조

- 본 stub 의 입력·응답 모양을 그대로 `gah.mcp.server` / `gah.mcp.tools` 에 구현.
- `list_labels` 의 `signature` 는 `LabelRegistry.label_catalog_signature()` 직접 위임.
- `labels_all` / `labels_any` / `labels_none` 필터는 `assets_fts MATCH 'label:...'` + `asset_labels` JOIN 로 풀어낸다 (M3 plan 에서 정확 SQL 결정).
- `matched_labels` 는 `asset_labels` 의 행을 `LabelScore` 그대로 반환.
- MCP 서버 `instructions` 필드에 본 문서 §1 ~ §4 요지를 한 문단으로 압축해 박아 둔다.

M3 끝에 이 stub 을 본격 가이드로 풀어쓰면서, 실제 응답 예시 / 에러 케이스 / `signature` 캐시 무효화 시점 / 통일성 가중치 튜닝 노트를 추가한다.
