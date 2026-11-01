# 고전 검색 저자 역할 수정 리뷰

기준: develop `1e2226e`. 이슈 #17의 문헌 저자·작품 작가 혼동을 해결한다. 기존 author/body 기본값을 유지하며 document_author, author_role, work_author=null, search_target을 추가한다. 서버 설명과 교사 안내에서 기사명 탐색과 본문 언급 탐색을 구분한다.

Claude Code를 도구 없이 실행해 diff와 전체 검색 구현·서버·캐시·계약·테스트·교사 안내를 제공했다. 실제 응답 모델 `claude-opus-4-7`은 develop 병합 승인, 확정 결함 없음을 보고했다. 호환 author 유지, 안내 길이, 서버 공통 지침의 분량에 대한 선택적 제안을 확인했다. 기존 클라이언트 호환성을 유지하기 위해 필드를 제거하지 않았다. body/title 캐시 키는 기존 section에 구분돼 있다.

Ponytail 리뷰: 기존 레코드를 반환하는 지점 한 곳을 수정하고 새 추상화·의존성·데이터를 추가하지 않았다. 같은 제목의 타 문헌 기사와 저자 누락, 본문/기사명 범위를 합성 XML로 검증했다. 추가 확정 결함 없음.

최종 검사: Ruff lint·format, mypy, pytest 104 passed / 1 skipped, Markdown lint 통과. 스킵은 TEST_MCP_URL 미설정인 원격 테스트다. production 동작 변경과 실제 교사 계정 검증은 이번 develop 통합에 포함하지 않는다.
