# Gravity Rotate (Pygame)

중력을 90도 회전시키며 목표 타일에 도달하는 타일 퍼즐 액션 게임입니다.

## 실행

1. Python 3.10+
2. 의존성 설치
   - `pip install -r requirements.txt`
3. 실행
   - `python main.py`

## 조작

- 좌클릭: 중력 반시계(CCW) 90도
- 우클릭: 중력 시계(CW) 90도
  - 기본값: `0` 키를 누르고 있을 때만 동작
  - 설정에서 자유 우클릭으로 변경 가능
- 터치: 화면 왼쪽(반시계), 오른쪽(시계)
- `ESC`: 일시정지/뒤로
- `R`: 현재 레벨 재시작
- `0`: 기본 설정에서 누르고 있는 동안 HUD 표시

## 주요 기능

- 메인 메뉴 / 레벨 브라우저 / 설정 / 결과 화면
- 레벨 브라우저 필터/검색/정렬/미리보기
- JSON 맵 자동 로드 (`map/*.json`, 파일명 사전순)
- 포탈 순환 텔레포트 + 재진입 쿨다운
- 스파이크 리스폰
- 저장(`save.json`)
  - 레벨 해금
  - 최고 기록(클릭 수 / 시간)
  - 설정값
    - 볼륨 / 전체화면 / 화면 배율 / 화면 흔들림
    - 우클릭 0키 필요 여부
    - HUD 표시 정책(0키 홀드)
    - 고대비 UI / 모션 감소
    - UI 글자 크기

## 맵 포맷

맵은 `agent.md` JSON 스펙을 따릅니다.

- 필수: `meta`, `tile_size`, `width`, `height`, `legend`, `grid`
- 선택: `meta.difficulty` (`tutorial|mid|hard`)
- 포탈: `PORTAL:n`

## 맵 감사 도구

`tools/map_audit.py`로 맵 스키마 및 기본 규칙을 검사할 수 있습니다.

- 실행:
  - `python -m tools.map_audit`
- 옵션:
  - `--no-left-click-check`
  - `--max-time-sec 12`
  - `--random-trials 120`

참고: `pygame`가 설치되지 않은 환경에서는 좌클릭 시뮬레이션을 자동 생략하고 스키마 검사만 수행합니다.
