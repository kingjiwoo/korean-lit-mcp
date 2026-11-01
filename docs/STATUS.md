# 현재 진행 상태

갱신일: 2026-11-01. 공개 MCP는 Vercel production에서 운영하며, main은 운영·develop은 다음 릴리스 통합 브랜치다. PR #14의 ITKC 발췌 검색은 릴리스 PR #15로 배포하고 실제 HTTP 검증을 마쳤다. PR #18의 저자 역할·검색 범위 수정은 develop에 통합했으며 아직 production에 반영하지 않았다. 내장 전문은 김유정 「동백꽃」·「봄·봄」 두 편이다. 국립중앙도서관 키는 신청 중이다.

## 구현과 리뷰

PR 00~09는 Codex가 책임지고 Claude Code의 실제 응답 모델 `claude-opus-4-7`에 읽기 전용 교차 리뷰를 맡겼다. 타당한 지적을 수정하고 ponytail 리뷰(간소화·회귀 검토)와 관련 검사를 실행했다. 단계별 근거는 [리뷰 기록](reviews/PR-00.md)부터 유지한다.

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

고전문학·고전시가의 공식 API와 이용조건 조사, 검색·원문 연결 및 문법 도구 계획은 [작업 계획 13절](IMPLEMENTATION-PLAN.md#13-고전문학고전시가-지원-계획)에 기록했다. 국립중앙도서관 API 키는 신청 중이며, 발급 뒤 실제 응답을 검증한다. 한국고전종합DB는 키 없이 실제 GO_BD·MO_BD·KP_BD·MO_GS 응답을 확인했다. 검색 발췌 도구는 production에서 검증했고, 전문 조회 경로와 현대 편집·번역 자료 이용조건은 추가 확인이 필요하다.

초기 스택 PR은 부모를 통합한 뒤 자식을 `develop` 대상으로 바꾸고 최신 이력을 병합했다. 원래 검토한 파일 내용이 유지되는지 확인한 뒤 새 커밋의 CI를 다시 통과시켰다. 실제 배포·교사 실증이 남았다는 이유만으로 코드 검증을 마친 작업 PR을 Draft에 묶어두지 않는다.

## 확인한 결과

- PR 00~08 당시 로컬 Ruff lint·format, mypy, Markdown lint와 78개 테스트를 통과했다. 공개 전환 후의 검증은 PR 09에 별도로 기록한다.
- PR 09에서 사용자 토큰·기관 키 없이 CLI를 기동하고 실제 HTTP를 포함한 75개 테스트를 통과했다. 제거한 비공개 인증 테스트가 있어 개수가 줄었다.
- Vercel ASGI 진입점과 배포 Host 환경설정 테스트 7개를 추가했다. 공개 Vercel URL의 실제 HTTP 조회·검증도 통과했다.
- Vercel 배포 보완 당시 전체 82개 테스트와 Ruff lint·format, mypy, Markdown lint를 통과했다. 실제 배포 HTTP 테스트를 포함한 결과다.
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
| Claude 커넥터 | 실제 Claude Code와 SDK의 공개 HTTP 호출 확인 | Claude 웹·학교 환경의 교사 실사용 실증 |
| 파일럿 성공 기준 | 원문 할루시네이션 문제는 기준 설계에서 확인됨 | 교사별 작품·판본·문제 유형과 반복 사용 기준 확인 |
| 추가 도구 | 파일럿 뒤 수요 확인 조건으로 계획됨 | 판본 비교·작가·어휘·방언·추천 도구의 실제 수요 확인 |

초기 공유 Bearer 토큰은 사용자의 공개 운영 결정으로 제거했다. 사용자에게 토큰·회원가입을 요구하지 않는다. `NL_API_KEY`는 외부 서지 검색을 사용할 때 운영 서버에만 선택적으로 설정하며, 생략해도 내장 원문·검증 도구는 동작한다. 공개 호출량은 프로세스 전체에서 공유하며 운영 플랫폼의 추가 요청량·비용 제한은 배포 시 확인한다.

공개 주소는 `https://korean-lit-mcp.vercel.app/mcp`다. 최종 릴리스와 production 배포 검증, 실제 교사 사용 여부를 별도로 기록하며 어느 하나의 성공으로 다른 항목을 완료 처리하지 않는다.

## 고전 검색 확장 진행

`search_classical_text` 도구를 추가해 PR #15로 production에 배포했다. 고전원문·한국문집총간·한국고전총간의 본문 및 기사명 검색을 지원하고, 운영자가 `ITKC_API_URL`을 설정한다. API 키·회원가입 없이 공식 검색 API와 새 클라이언트의 실제 호출을 확인했다. 전문 공급과 문법 분석은 구현되지 않았고, 상세 API·근거자료 확보가 남았다. 이 도구가 모든 국문 시가·소설을 지원한다고 표시하지 않는다. 후속 단계별 진행 상태는 [조사 기록](decisions/0002-itkc-search.md)을 따른다.

## 키 없는 후속 작업과 한계

PR #18 이후 필수 검사는 pytest 104 passed / 1 skipped와 Ruff lint·format, mypy, Markdown lint 통과다. 이번 수정의 로컬 MCP 실제 사미인곡 body/title 호출에서 저자 역할·작품 작가 미확인 필드를 확인했다. 별도 키 없는 호출로 GO_GS·KP_GS도 확인해 기존 GO_BD·MO_BD·KP_BD·MO_GS와 함께 세 컬렉션의 두 검색 대상을 모두 실증했다. 원격 테스트 1개는 production 미배포라 실행하지 않았다.

- [PR #18](https://github.com/kingjiwoo/korean-lit-mcp/pull/18): 문헌 저자 document_author, 호환 author의 역할, 미확인 work_author=null, search_target 표시를 develop에 통합했다. 이슈 #17 재현은 합성 XML로 검사했다.
- [PR #20](https://github.com/kingjiwoo/korean-lit-mcp/pull/20)의 [키 없는 출처 실증](decisions/0003-keyless-sources.md): 한국학자료센터 공개 문헌정보 API에서 구운몽 11건·洪吉童傳 3건·송강가사 4건을 관측했다. 목록 수이며 전문 공급 수가 아니다. Python HTTPS 연결 및 전문 API 응답이 미확인이라 커넥터는 추가하지 않았다.
- [문법 도구 계약](GRAMMAR-TOOL-PLAN.md): 현대/중세/근대, 출처·용례·적용 범위·오류·검사 기준을 정했다. 검수 자료 확보가 남았고 문법 MCP 도구는 등록하지 않았다. 한국어기초사전 API는 별도 키가 필요하다.
- README를 네 도구의 실제 지원 범위·설정·사용 예시·미지원 항목에 맞춰 갱신했다. 문서의 develop 상태와 운영 배포 상태를 구분한다.

이번 후속 작업은 develop 통합까지다. 키 없는 작업 전체가 국립중앙도서관 승인에 묶인 것은 아니지만, 전문 공급·자료 재사용·새 출처 HTTPS 호환성은 별도 선행 조건이다. 사용자에게 즉시 답변이 필요한 제품 선택은 없다.

## 교육용 원문 확보·검증 보강 (2026-11-01)

키 없는 후속 구현을 두 PR로 분리했다. [PR #33](https://github.com/kingjiwoo/korean-lit-mcp/pull/33)은 세 작품의 발견용 이칭·귀속 근거와 ITKC 검색 레코드를 구분한다. PR-D(#31)는 실제 요청·검색 범위·검수 목록 수와 검색 결과 상태, 원문 미확보 시 안내, 검증 기준과 한계를 응답에 표시한다. 본문 공급이나 서버 LLM 기능은 추가하지 않았다.

PR-A 로컬 검사는 111 passed / 1 skipped이며 필수 정적·문서 검사도 통과했다. Claude Opus 교차 리뷰 호출은 사용량 제한(429, 리뷰 토큰 0)으로 실패했다. 당시 자체 검토·로컬 검사·CI 성공을 교차 리뷰 성공으로 간주하지 않고 초안 PR로 보류했다. 이후 사용자 승인으로 Claude 리뷰만 생략하기로 했다. 운영 배포와 NL 인증 실증은 수행하지 않았다.

PR-A와 PR-D를 함께 적용한 최종 로컬 검사는 121 passed / 1 skipped와 Ruff lint·format, mypy, Markdown lint 통과다. 원격 production 검사는 실행하지 않았다. PR-D는 PR-A 브랜치 위에 쌓았으며, PR-A를 develop에 squash 통합한 뒤 후속 PR의 대상을 develop으로 바꾸고 최신 develop을 정상 병합해 CI를 다시 확인한다. 두 PR 모두 Claude Opus 리뷰 호출이 429 사용량 제한으로 실패해 당시 초안 상태로 남겼다. Codex 자체 ponytail 검토에서는 호출부·직렬화·부분 실패·검증 기준·입력 비보관을 확인했고 미해결 결함은 찾지 못했다. 독립 교차 리뷰를 대체한 것으로 표시하지 않는다.

별도 실제 ITKC 무키 기사명 검색을 현재 코드로 확인했다(2026-11-01, collection=classic, limit=3). 규원가는 2개 검색 레코드가 검수 이칭 불일치로, 사미인곡은 1개 제목 후보로 표시됐고 홍길동전은 해당 범위에서 0건이었다. 세 검색어 모두 발견용 작품 후보는 반환됐지만 검색 레코드의 `available_text`는 전부 false다. 이는 새 전문 공급·동일 작품 확정·모든 컬렉션 부재의 검증이 아니다. NL 인증 API와 실제 교사 클라이언트 동작은 확인하지 않았다.

2026-11-01 사용자가 사용량 제한 시 Claude 교차 리뷰를 생략하고, 검사 통과 시 develop에 병합한 뒤 main까지 릴리스하도록 명시적으로 승인했다. PR #33은 `95a5d31`로 develop에 squash 통합했고, PR #34는 대상을 develop으로 바꿔 최신 develop을 정상 병합했다. 독립 교차 리뷰를 통과했다고 표시하지 않으며 Codex 자체 검토·필수 검사·CI를 유지한다. 최종 main 릴리스와 배포 SHA·운영 검증 결과는 GitHub 릴리스 PR에 기록한다.
