# 현재 진행 상태

갱신일: 2026-10-27. SQLite·ORM·별도 캐시 서버 없이 파일 원문과 메모리 TTL 캐시로 구현했다. `main`과 `develop`은 아직 초기 커밋이며, 구현은 아래 스택 PR에서 검토한다.

## 구현과 리뷰

PR 00~08은 Codex가 책임지고 Claude Code의 실제 응답 모델 `claude-opus-4-7`에 읽기 전용 교차 리뷰를 맡겼다. 타당한 지적을 수정하고 ponytail 리뷰와 관련 검사를 실행했다. 단계별 근거는 [리뷰 기록](reviews/PR-00.md)부터 유지한다.

| 단계 | 브랜치 | PR | 상태 |
| --- | --- | --- | --- |
| PR 00 | `chore/project-foundation` | [#1](https://github.com/kingjiwoo/korean-lit-mcp/pull/1) | 구현·검증, GitHub Python·Markdown CI 통과 |
| PR 01 | `feature/mcp-contracts` | [#2](https://github.com/kingjiwoo/korean-lit-mcp/pull/2) | 입력·응답 계약과 MCP 통신 검증 |
| PR 02 | `feature/text-source` | [#3](https://github.com/kingjiwoo/korean-lit-mcp/pull/3) | 실제 만료 TXT 2작품과 무결성 검증 |
| PR 03 | `feature/passage-search` | [#4](https://github.com/kingjiwoo/korean-lit-mcp/pull/4) | 작품 검색·판본·범위 조회 검증 |
| PR 04 | `feature/quote-verification` | [#5](https://github.com/kingjiwoo/korean-lit-mcp/pull/5) | 인용 판정·위치·교정 후보 검증 |
| PR 05 | `feature/draft-verification` | [#6](https://github.com/kingjiwoo/korean-lit-mcp/pull/6) | 명시된 인용 표시 추출·검사 범위 검증 |
| PR 06 | `feature/upstream-cache` | [#7](https://github.com/kingjiwoo/korean-lit-mcp/pull/7) | 캐시·모의 API 검증, 실제 인증 검색 대기 |
| PR 07 | `feature/remote-operation` | [#8](https://github.com/kingjiwoo/korean-lit-mcp/pull/8) | 인증·HTTP 제한·비루트 컨테이너 검증 |
| PR 08 | `chore/pilot-deployment` | [#9](https://github.com/kingjiwoo/korean-lit-mcp/pull/9) | Python·Markdown·컨테이너 CI 통과, 원격 배포·교사 실증 대기 |

Draft PR은 실제 외부 검증이나 사람의 검토를 통과했다는 뜻이 아니다. 순서대로 부모 PR을 통합한 뒤 자식 PR을 `develop` 대상으로 바꾼다. squash 통합 후에는 최신 `develop`을 자식 작업 브랜치에 정상 병합하고 다시 검사해 중복 diff를 정리한다.

## 확인한 결과

- 로컬 Ruff lint·format, mypy, Markdown lint와 78개 테스트 통과.
- Docker 이미지 빌드 성공. 읽기 전용 파일시스템·비루트 컨테이너에서 실제 HTTP 조회 → 판본·해시 전달 → 인용 검증을 확인했다.
- 이전 MCP `2025-11-25` 초기화와 현재 SDK 클라이언트 호출을 실제 HTTP로 확인했다.
- 공유마당의 「동백꽃」·「봄·봄」 제공 파일과 권리 표시를 직접 확인했다. 원문 파일은 편집하지 않았으며 제공 TXT의 물리 행을 주소로 사용한다.
- 공통 검사 스킬의 두 진입점이 같은 파일을 읽는지와 형식을 확인했다. Codex app-server의 `skills/list`에서 repo 범위·enabled 상태를, Claude Code의 실제 `/check-project` 로딩에서 경로와 검사 명령을 확인했다.
- PR #1~#8의 GitHub Python·Markdown CI가 모두 통과했다.
- PR #9의 GitHub Python·Markdown·컨테이너 CI도 통과했다. 컨테이너 준비 중 연결 재설정을 재시도하도록 수정하고 실제 CI에서 확인했다.

## 외부 입력이 필요한 작업

| 항목 | 현재 근거 | 다음에 필요한 것 |
| --- | --- | --- |
| 인증된 서지 검색 | 실제 키 없는 인증 오류·합성 응답 테스트만 확인 | 서버 환경에 `NL_API_KEY` 설정 후 실제 성공 XML·필드·쿼터 검증 |
| 원격 배포 | 컨테이너 실행·운영 안내와 CI 준비 | 호스팅 플랫폼·계정·서비스·예산, 운영용 비밀값과 실제 Host 확정 |
| Claude 커넥터 | 일반 MCP SDK의 HTTP 통신 검증 | 교사 계정에서 커넥터·고정 인증 헤더 연결 실증 |
| 파일럿 성공 기준 | 원문 할루시네이션 문제는 기준 설계에서 확인됨 | 교사별 작품·판본·문제 유형과 반복 사용 기준 확인 |
| 추가 도구 | 파일럿 뒤 수요 확인 조건으로 계획됨 | 판본 비교·작가·어휘·방언·추천 도구의 실제 수요 확인 |

파일럿 인증은 Bearer 헤더를 기본 구현했다. 초기 설계의 URL 한 번 입력 방식보다 설정 단계가 추가되므로 실제 교사의 연결 편의성을 확인한 뒤 확정한다. 접근 토큰·기관 키는 채팅이나 Git에 붙이지 않고 비밀 관리 또는 실행 환경으로 전달한다.

호스팅과 교사 실사용 확인 전에는 staging·production 배포나 릴리스 완료를 표시하지 않는다.
