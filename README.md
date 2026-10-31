# korean-lit-mcp

국어 교사를 위한 한국문학 MCP — 원문을 글자 그대로 가져오고, 문제 속 인용을 원문과 대조해 검증합니다.

## 개발 환경

Python 3.13과 [uv](https://docs.astral.sh/uv/), 문서 검사에만 Node.js 24를 사용합니다.

```sh
uv sync --frozen
npm ci --ignore-scripts
uv run ruff check .
uv run ruff format --check .
uv run mypy src
uv run pytest
npm run lint:md
```

기관 API 키 없이 로컬 검사를 실행할 수 있습니다. 비밀값은 `.env.example`의 변수명을 참고해 환경변수로 전달합니다. `.env` 파일은 자동으로 로딩하지 않습니다.

## 현재 기능

- 공유마당 만료 TXT 두 작품(김유정 「동백꽃」·「봄·봄」)의 검색과 원문 조회
- 제출한 인용과 지원하는 초안 표시의 정확 일치·표기 차이·불일치 검사
- 판본·해시·출처와 검사 범위 표시, 교사 제공 본문은 요청 중에만 처리
- 선택적인 국립중앙도서관 서지 검색과 크기 제한 메모리 TTL 캐시
- Bearer 인증·호출 제한을 적용한 원격 HTTP 서버와 비루트 컨테이너

실행에는 비공개 `MCP_AUTH_TOKEN`이 필요합니다. 원문 TXT의 행 주소는 교과서 문단과 다를 수 있습니다. 인증된 기관 검색 성공, 실제 Claude 계정 연결, 원격 배포와 교사 파일럿은 별도 실증 항목입니다.

## 개발 문서

- [Claude 작업 규칙](CLAUDE.md)
- [Codex/에이전트 작업 규칙](AGENTS.md)
- [스킬 운영 체계](docs/SKILLS.md)
- [브랜치 및 배포 전략](docs/BRANCHING-AND-DEPLOYMENT.md)
- [구현 작업 계획](docs/IMPLEMENTATION-PLAN.md)
- [현재 진행 상태](docs/STATUS.md)
- [교사 사용 안내](docs/TEACHER-GUIDE.md)
- [운영·배포 안내](docs/OPERATIONS.md)
