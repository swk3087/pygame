# agent.md — Pygame “Gravity Rotate” Tile Game (Codex 작업 지시서)

> 목표: **클릭/터치 1개 조작만**으로 플레이하는, **심플하지만 고급스러운** 타일 기반 퍼즐 액션 게임을 Python + Pygame으로 구현한다.  
> 핵심 메커닉: **플레이어(네모)는 항상 현재 중력 방향으로 가속/이동**하며, **클릭 시 중력이 시계 반대방향(CCW)으로 90° 회전**한다.  
> 레벨은 `/map` 폴더의 맵 파일(JSON)로 로드된다. (향후 Node.js 서버로 맵 제작/배포 확장 예정)

---

## 0) “완성도” 기준 (필수)
- 실행 즉시 크래시 없이 구동
- 메뉴/튜토리얼/설정/일시정지/레벨 완료 화면 포함
- 클릭/터치 입력 모두 지원 (마우스 + 모바일 터치 이벤트)
- 레벨 파일만 추가하면 자동으로 레벨 리스트에 반영
- 저장 데이터(클리어/해금) 로컬에 저장 (예: `save.json`)
- 심플한 연출(부드러운 전환, 약한 카메라 흔들림/이펙트, 깔끔한 UI)

---

## 1) 게임 컨셉/플레이 규칙

### 1.1 플레이어
- 형태: 정사각형 AABB
- 속성:
  - 위치 `pos (x,y)`, 속도 `vel (x,y)`
  - 크기 `PLAYER_SIZE`
  - 최대 속도 `MAX_SPEED`
- 물리:
  - 매 프레임 `vel += gravity_vec * GRAVITY_ACC * dt`
  - `pos += vel * dt`
  - 타일 충돌 처리(벽/바닥/천장) 후 속도 보정

### 1.2 중력 회전 (원버튼)
- 입력(클릭/터치) 시:
  - `gravity_dir = (gravity_dir + 1) mod 4`  (CCW 90°)
  - **속도 벡터도 동일하게 90° CCW 회전** (관성 유지로 고급스러운 느낌)
    - (vx, vy) -> (-vy, vx)
- 회전 직후 1~2프레임 정도 “입력 버퍼/쿨타임”을 둘 수 있음(연타로 인한 이상 동작 방지)

### 1.3 목표
- `GOAL` 타일과 플레이어 AABB가 겹치면 레벨 클리어
- 클리어 시: 타임/클릭 수/데스 수(선택) 기록 가능 (발표 자료용)

### 1.4 장애물(선택)
- `SPIKE`(가시) 타일에 닿으면 리스폰
- 리스폰 위치는 `spawn` 또는 체크포인트(선택)

### 1.5 포탈(필수로 넣기)
- 포탈은 **짝/그룹**으로 동작:
  - 같은 `portal_id`를 가진 포탈 타일들 중 **다음 포탈**로 텔레포트 (순환) 또는 2개면 서로 왕복
- 텔레포트 규칙:
  - 플레이어 중심을 목적지 포탈 중심으로 이동
  - 속도는 유지(기본), 단 “즉시 재진입” 방지용 쿨다운(예: 0.2s) 필수
- 연출:
  - 텔레포트 시 짧은 플래시/잔상/사운드

---

## 2) 레벨(맵) 시스템: 타일 기반

### 2.1 타일 방식
- 마크처럼: 격자(그리드) 타일
- 타일 크기: 기본 32px (맵마다 다르게 가능)
- 레벨이 올라갈수록:
  - 맵 가로/세로 증가
  - “빈 공간 대비 타일(벽/장애물) 총량 증가”
  - 포탈/가시/구조 요소 증가

### 2.2 `/map` 폴더 구조
- `/map/001_tutorial.json`
- `/map/002_basic.json`
- `/map/003_portal.json`
- ...
- 파일명 정렬(사전순)로 레벨 순서를 결정

---

## 3) 맵 파일 포맷 (JSON) — **반드시 이 스펙으로**
> 향후 Node.js 서버/에디터와 호환을 위해 텍스트(ASCII)보다 JSON을 사용한다.

### 3.1 JSON 스키마
```json
{
  "meta": {
    "id": "001_tutorial",
    "name": "Tutorial",
    "author": "map-maker",
    "version": 1
  },
  "tile_size": 32,
  "width": 20,
  "height": 12,

  "legend": {
    ".": "EMPTY",
    "#": "WALL",
    "S": "SPAWN",
    "G": "GOAL",
    "^": "SPIKE",
    "A": "PORTAL:1",
    "B": "PORTAL:2"
  },

  "grid": [
    "####################",
    "#S.....#..........G#",
    "#......#...........#",
    "#......#...........#",
    "#......#...........#",
    "#......#...........#",
    "#......#...........#",
    "#......#...........#",
    "#......#...........#",
    "#......#...........#",
    "#......#...........#",
    "####################"
  ],

  "tutorial": [
    { "type": "text", "at": [2, 1], "message": "Click to rotate gravity (CCW 90°)." },
    { "type": "text", "at": [2, 2], "message": "Reach the goal tile to clear." }
  ],

  "rules": {
    "time_limit_sec": null,
    "allow_spikes": true
  }
}
3.2 파싱 규칙

width/height는 grid의 문자열 길이 및 줄 수와 일치해야 함 (불일치 시 에러 로그 후 안전 종료)

legend는 문자 -> 타일 타입 매핑

PORTAL:n 형식은 포탈 그룹 id 로 인식

S(SPAWN)는 1개만 허용(여러 개면 첫 번째만 사용 + 경고 로그)

G(GOAL)도 1개 권장(여러 개면 모두 목표로 인정 가능)

4) 씬/화면 구성 (필수)
4.1 Scene 목록

MainMenuScene

Start / Level Select / Settings / Quit

LevelSelectScene

/map 로드한 레벨 목록 표시

저장 데이터 기반으로 해금 표시

SettingsScene

Master Volume (0~100)

Fullscreen On/Off

Screen Scale (1x/2x/3x) 또는 해상도 선택

Vibration(없으면 옵션만) / Screen shake On/Off(선택)

GameScene

실제 플레이

HUD: 레벨명, 클릭수, 타이머(선택)

Pause 메뉴(ESC 또는 UI 버튼)

ResultsScene

Clear! / stats / Next / Retry / Back

TutorialOverlay (GameScene 안에서 오버레이로 구현 가능)

맵 JSON의 tutorial 배열을 읽어 표시

4.2 조작

기본: 좌클릭/터치 = 중력 회전

보조(키보드):

ESC = 일시정지/메뉴

R = 리스타트

대회 요구가 “단순 조작”이라도, 테스트/편의용 단축키는 허용.

5) 렌더링/연출 (심플하지만 고급스럽게)
5.1 해상도/스케일링

내부 논리 해상도(예): BASE_W=960, BASE_H=540

실제 창 크기는 설정의 스케일로 확대

모든 렌더는 base_surface에 그린 뒤 pygame.transform.scale로 화면에 출력

5.2 스타일

배경: 단색 또는 그라데이션 느낌(간단히 Surface + alpha)

타일: 단순한 색 블록 + 얇은 테두리/그림자

플레이어: 강조색(하나의 포인트 컬러)

포탈: 링/파동 애니메이션(간단한 원 그리기/스프라이트)

5.3 효과(가벼운 것만)

클릭 시 작은 파티클 10~20개 (원/사각형)

텔레포트 플래시(1~2프레임 밝기 증가)

선택: 아주 약한 카메라 쉐이크 (설정에서 끄기 가능)

6) 충돌 처리(핵심 구현)
6.1 타일 충돌

플레이어는 AABB

충돌 판정은 주변 타일만 검사:

플레이어 AABB가 포함하는 타일 범위 + 1칸 여유

분리해결:

pos.x 이동 후 x축 충돌 해결

pos.y 이동 후 y축 충돌 해결

벽에 박히면 해당 축 속도를 0으로

안정성:

dt 급증(창 이동/일시정지 후) 시 dt clamp (dt = min(dt, 1/30))

6.2 스파이크/골/포탈 판정

해당 타일의 rect와 플레이어 rect 충돌로 처리

포탈은 재진입 쿨다운으로 루프 방지

7) 저장 데이터 (save)

파일: save.json

내용:

unlocked_level_count

레벨별 최고 기록(클릭 수/시간)

설정값(볼륨, 풀스크린, 스케일)

저장/로드 실패 시:

기본값으로 시작 + 로그 출력

8) 프로젝트 구조(폴더/파일) — 이대로 생성
project/
  main.py
  requirements.txt
  README.md
  agent.md

  core/
    __init__.py
    game.py            # 루프/윈도우/스케일링/전역 리소스
    scene_manager.py   # scene stack 관리 (push/pop/replace)
    config.py          # 기본 설정/상수
    assets.py          # 사운드/폰트/이미지 로드
    save.py            # save.json load/save
    utils.py           # clamp, lerp, rotate_vec_ccw 등

  scenes/
    __init__.py
    main_menu.py
    level_select.py
    settings.py
    game_scene.py
    results.py

  gameplay/
    __init__.py
    tilemap.py         # 맵 로드/타일 queries/collision helpers
    player.py
    portal.py          # portal logic (id groups, cooldown)
    particles.py       # 간단한 파티클

  assets/
    fonts/
    sfx/
    img/

  map/
    001_tutorial.json
    002_basic.json
    003_portal.json
9) 라이브러리/환경

Python 3.10+ 권장

Pygame 2.5+ 권장

requirements.txt

최소:

pygame>=2.5.0

외부 라이브러리는 최대한 안 쓰기(심플 유지)

10) 구현 단계(체크리스트) — Codex는 순서대로 진행
Phase 1: 뼈대

 프로젝트 구조 생성

 main.py에서 Game 시작

 SceneManager 동작 (MainMenuScene 표시)

 설정 로드/저장 기본

Acceptance

실행하면 메인 메뉴가 뜨고 Quit로 정상 종료

Phase 2: 맵 로더/렌더

 /map 폴더의 json 목록 로드/정렬

 JSON 스펙 검증

 TileMap 클래스 구현(타일 조회, rect 계산)

 타일 렌더링

Acceptance

튜토리얼 맵이 화면에 정상 표시

Phase 3: 플레이어 물리/충돌

 Player 업데이트(dt), 중력 적용, 속도 clamp

 타일 충돌 해결(안정적으로 벽에 안 박힘)

 클릭/터치로 중력 CCW 회전 + 속도 CCW 회전

Acceptance

클릭만으로 벽/바닥을 타고 움직일 수 있음

Phase 4: Goal/Reset/Pause

 골 타일 도착 시 클리어 처리

 R 리스타트, ESC 일시정지 메뉴

 ResultsScene로 전환(Next/Retry/Back)

Acceptance

레벨 클리어 → 결과 화면 → 다음 레벨 이동

Phase 5: 포탈

 PORTAL 그룹 파싱 (PORTAL:n)

 포탈 진입 시 목적지로 이동 + 쿨다운

 연출(사운드/플래시)

Acceptance

포탈 2개 이상 있는 맵에서 정상 텔레포트, 무한루프 없음

Phase 6: 메뉴/설정/튜토리얼

 MainMenu/LevelSelect/Settings UI 완성

 튜토리얼 텍스트 오버레이 표시(맵 tutorial 배열)

 설정 저장(볼륨/스케일/풀스크린)

Acceptance

설정 변경 후 재실행해도 유지됨

Phase 7: 폴리시(고급스러움)

 파티클(클릭/텔레포트/클리어)

 부드러운 전환(페이드 인/아웃)

 아주 약한 카메라 쉐이크 옵션

Acceptance

“단순하지만 완성도 높다” 느낌의 피드백이 나올 정도

11) 코딩 규칙 (엄격)

PEP8 준수, 함수/클래스에 type hints

전역 남발 금지 (config는 상수만)

씬 간 데이터 전달은 Game 또는 SceneManager를 통해 최소화

dt 기반으로만 움직이기(프레임 의존 금지)

예외/에러는 사용자에게 친절한 메시지 + 콘솔 로그

12) QA 체크리스트

 창 크기 변경/풀스크린 전환 시 비율 유지

 dt 튐 방지(clamp) 적용

 포탈 재진입 루프 없음

 맵 JSON 오류 시 크래시 대신 “맵 로드 실패” 메시지

 클릭/터치 이벤트 모두 동작

 zip 제출 시 map/, requirements.txt, 소스 포함

13) (미래 확장) Node.js 맵 서버 호환 아이디어 

나중에 맵 제작/배포를 쉽게 하려면 아래 형식으로 HTTP 제공 가능

GET /maps → 맵 목록(메타만)

GET /maps/:id → 위 JSON 그대로 반환

클라이언트는:

로컬 /map 우선 로드

옵션으로 서버에서 내려받아 downloaded_map/ 캐시

14) “대회 제출” 참고 (코드 외)

AI 활용 시:

발표자료에 “AI로 초안 생성 → 직접 수정/검증” 형태로 명시

발표자료 10장 이내에서 강조할 것:

중력 회전 메커닉

타일 기반 맵 로딩(JSON)

포탈/튜토리얼/설정/저장(완성도)

15) Done 정의 (최종)

튜토리얼 포함 최소 5개 레벨

메뉴/설정/레벨선택/결과화면 완비

포탈 포함

클릭/터치 원버튼 플레이 성립

버그/크래시 없이 ZIP 제출 가능