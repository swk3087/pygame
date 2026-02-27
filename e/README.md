# `/e` Standalone Map Maker

게임 런타임과 분리된 웹 기반 맵메이커입니다.  
저장 대상은 `/e/maps`만 허용되며 `/map`은 직접 수정하지 않습니다.

## 실행

```bash
cd e
npm install
npm run dev
```

브라우저에서 `http://localhost:5173` 접속.

## 주요 기능

- 타일 페인트/지우기(우클릭 지우개)
- 사각 채우기
- 포탈 ID 페인트(`PORTAL:n` 자동 문자 매핑)
- 사각 선택, 복사/붙여넣기
- Undo/Redo (`Ctrl+Z`, `Ctrl+Y`)
- 맵 저장/불러오기(`/e/maps`)
- 게임 JSON 스펙 검증(`/api/validate`)

## 단축키

- `Ctrl+Z` / `Ctrl+Y`: Undo / Redo
- `Ctrl+C` / `Ctrl+V`: 복사 / 붙여넣기
- `Ctrl+S`: 저장
- `Delete`: 선택 영역 지우기
- `Space + Drag`: 팬 이동
- `Wheel`: 줌
- `Esc`: 드래그/붙여넣기 취소

## API

- `GET /api/maps`
- `GET /api/maps/:filename`
- `POST /api/maps`
- `POST /api/validate`

