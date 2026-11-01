# README·진행 상태 정리 리뷰

기준: develop `ff6614e`. 네 도구의 실제 범위, 호출 예시, 환경설정, 검사와 미지원 기능을 README에 정리하고 STATUS의 현재 상태를 갱신한다. 다른 세션에서 PR #19로 반영한 제품 실행 경로 LLM 호출 금지 문구를 보존했다.

Claude Code에 도구 없이 제안 README/STATUS와 관련 검색·서버·서지·원문·진입점·HTTP 테스트, 출처·문법 설계 문서를 제공했다. 실제 응답 모델은 `claude-opus-4-7`이다. 리뷰가 지적한 URL 조건, NL_API_KEY 활성화 조건, 최신 검사 수를 보강했다. GO_GS·KP_GS도 실제 호출해 지원 조합 실증을 보완했다. 역사적 Opus 리뷰 문구는 기존 PR-00/PR-09 기록에 근거함을 확인했고 문서 링크와 13절 제목도 확인했다. 새 기능이나 제품 LLM 호출은 추가하지 않았다.

Ponytail 리뷰: README는 연결·네 도구·예시·환경변수·검사·남은 작업을 중심으로 구성하고 세부 절차는 기존 안내로 연결한다. 검색 발췌를 전문으로, 문법 계약을 구현 완료로 표시하지 않는다. develop과 production 상태를 구분한다. 추가 확정 결함 없음.

최종 검사: Ruff lint·format, mypy, pytest 104 passed / 1 skipped, Markdown lint 통과. 이번 실행에서 실제 로컬 MCP 사미인곡 body/title 응답의 저자 역할을 확인했다. 원격 production 테스트·배포는 이번 범위가 아니다. 한국학자료센터 HTTPS·전문 공급과 검수 문법 자료 확보가 남아 있다.
