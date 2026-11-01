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

- `search_classical_text`: 운영자가 `ITKC_API_URL`을 설정하면 한국고전종합DB의 본문·기사명 검색 발췌 제공. 전문 조회·검수 판본과 구분

- 공유마당 만료 TXT 두 작품(김유정 「동백꽃」·「봄·봄」)의 검색과 원문 조회
- 제출한 인용과 지원하는 초안 표시의 정확 일치·표기 차이·불일치 검사
- 판본·해시·출처와 검사 범위 표시, 교사 제공 본문은 요청 중에만 처리
- 선택적인 국립중앙도서관 서지 검색과 크기 제한 메모리 TTL 캐시
- 로그인 없이 연결하며 입력·호출 제한을 적용한 공개 HTTP 서버와 비루트 컨테이너

한 사람이 서버를 배포하면 사용자는 공개 MCP URL만 등록해 연결합니다. 회원가입·사용자 키 발급·인증 헤더는 필요하지 않습니다. `NL_API_KEY`는 외부 서지 검색을 추가할 때 운영자가 서버에만 설정합니다. 생략해도 내장 원문 조회와 인용 검증은 동작합니다.

서버와 MCP 도구 내부의 LLM 호출은 설계에서 제외합니다. 외부 모델 API·로컬 모델·MCP sampling·다른 서비스나 프로세스를 통한 LLM 추론 위임·실패 시 LLM 대체도 사용하지 않습니다. 도구는 근거 자료 조회와 일반 코드 검증을 제공하고, 해석·문항 생성·의미 판단은 사용자가 연결한 Claude 등 클라이언트 LLM이 수행합니다. 서버 운영에 별도 LLM 키나 모델 설정은 필요하지 않습니다.

로컬 서버는 `uv run python -m korean_lit_mcp`로 실행합니다. MCP 주소는 `http://127.0.0.1:8000/mcp`입니다. 원문 TXT의 행 주소는 교과서 문단과 다를 수 있습니다. 인증된 기관 검색 성공, 실제 Claude 계정 연결, 원격 배포와 교사 파일럿은 별도 실증 항목입니다.

공개 MCP 주소는 `https://korean-lit-mcp.vercel.app/mcp`입니다. Claude의 커스텀 커넥터에 이 주소를 등록하고 로그인 없는 방식으로 연결합니다. Vercel은 루트 `app.py`를 ASGI 앱으로 실행하고, 원문 파일은 배포에 포함합니다. 배포·환경변수·검증 절차는 [운영 안내](docs/OPERATIONS.md)를 따릅니다.

## 개발 문서

- [Claude 작업 규칙](CLAUDE.md)
- [Codex/에이전트 작업 규칙](AGENTS.md)
- [스킬 운영 체계](docs/SKILLS.md)
- [브랜치 및 배포 전략](docs/BRANCHING-AND-DEPLOYMENT.md)
- [구현 작업 계획](docs/IMPLEMENTATION-PLAN.md)
- [현재 진행 상태](docs/STATUS.md)
- [교사 사용 안내](docs/TEACHER-GUIDE.md)
- [운영·배포 안내](docs/OPERATIONS.md)
