# 현재 진행 상태

갱신일: 2026-11-01. SQLite·ORM·별도 캐시 서버 없이 파일 원문과 메모리 TTL 캐시로 구현했다. PR #1~#10은 CI를 재확인하고 `develop`에 모두 squash 병합했다. Vercel ASGI 설정과 공개 URL의 실제 MCP 호출도 검증했다. `develop`은 통합 브랜치, `main`은 Vercel production 브랜치다.

## 구현과 리뷰

PR 00~09는 Codex가 책임지고 Claude Code의 실제 응답 모델 `claude-opus-4-7`에 읽기 전용 교차 리뷰를 맡겼다. 타당한 지적을 수정하고 ponytail 리뷰와 관련 검사를 실행했다. 단계별 근거는 [리뷰 기록](reviews/PR-00.md)부터 유지한다.

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
| PR 09 | `feature/public-access` | [#10](https://github.com/kingjiwoo/korean-lit-mcp/pull/10) | 사용자 인증 제거·공개 연결 안내, Opus·ponytail 리뷰와 로컬 75개 테스트 통과 |

초기 스택 PR은 부모를 통합한 뒤 자식을 `develop` 대상으로 바꾸고 최신 이력을 병합했다. 원래 검토한 파일 내용이 유지되는지 확인한 뒤 새 커밋의 CI를 다시 통과시켰다. 실제 배포·교사 실증이 남았다는 이유만으로 코드 검증을 마친 작업 PR을 Draft에 묶어두지 않는다.

## 확인한 결과

- PR 00~08 당시 로컬 Ruff lint·format, mypy, Markdown lint와 78개 테스트를 통과했다. 공개 전환 후의 검증은 PR 09에 별도로 기록한다.
- PR 09에서 사용자 토큰·기관 키 없이 CLI를 기동하고 실제 HTTP를 포함한 75개 테스트를 통과했다. 제거한 비공개 인증 테스트가 있어 개수가 줄었다.
- Vercel ASGI 진입점과 배포 Host 환경설정 테스트 7개를 추가했다. 공개 Vercel URL의 실제 HTTP 조회·검증도 통과했다.
- Vercel 배포 보완 후 전체 82개 테스트와 Ruff lint·format, mypy, Markdown lint를 통과했다. 실제 배포 HTTP 테스트를 포함한 결과다.
- 실제 Claude Code가 공개 Vercel MCP의 검색 → 원문 조회 → 인용 검증을 호출했고 `all_submitted_exact=true`를 확인했다. Claude 웹·학교 환경에서의 교사 실사용과는 구분한다.
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
| Claude 커넥터 | 일반 MCP SDK의 HTTP 통신 검증 | 교사 계정에서 URL만 등록하는 공개 연결 실증 |
| 파일럿 성공 기준 | 원문 할루시네이션 문제는 기준 설계에서 확인됨 | 교사별 작품·판본·문제 유형과 반복 사용 기준 확인 |
| 추가 도구 | 파일럿 뒤 수요 확인 조건으로 계획됨 | 판본 비교·작가·어휘·방언·추천 도구의 실제 수요 확인 |

초기 공유 Bearer 토큰은 사용자의 공개 운영 결정으로 제거했다. 사용자에게 토큰·회원가입을 요구하지 않는다. `NL_API_KEY`는 외부 서지 검색을 사용할 때 운영 서버에만 선택적으로 설정하며, 생략해도 내장 원문·검증 도구는 동작한다. 공개 호출량은 프로세스 전체에서 공유하며 운영 플랫폼의 추가 요청량·비용 제한은 배포 시 확인한다.

공개 주소는 `https://korean-lit-mcp.vercel.app/mcp`다. 최종 릴리스와 production 배포 검증, 실제 교사 사용 여부를 별도로 기록하며 어느 하나의 성공으로 다른 항목을 완료 처리하지 않는다.
