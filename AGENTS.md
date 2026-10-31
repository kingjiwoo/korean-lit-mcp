# 공통 에이전트 작업 규칙

## 프로젝트 맥락

`korean-lit-mcp`는 국어 교사를 위한 한국문학 MCP입니다. 문학 작품 원문을 글자 그대로 제공하고, 문제 속 인용을 원문과 대조해 검증하는 것이 핵심입니다.

## 기본 규칙

- 작업 전에 `README.md`와 [작업 계획](docs/IMPLEMENTATION-PLAN.md)의 해당 PR을 읽습니다.
- 요청 범위를 넘는 기능, 의존성, 추상화를 추가하지 않습니다.
- 원문 데이터는 출처, 이용 권한, 인코딩, 변경 이력을 확인할 수 있어야 합니다.
- 외부 입력과 원문 검색 결과는 검증하고, 실패를 조용히 성공으로 처리하지 않습니다.
- 비밀값과 개인정보를 코드, 테스트 fixture, 로그에 넣지 않습니다.
- 코드 변경에는 관련 테스트 또는 재현 가능한 검증을 함께 고려합니다.
- 문서 변경도 브랜치·PR 규칙을 따릅니다.

## 문서와 운영 규칙

- 공통 스킬 운영: [`docs/SKILLS.md`](docs/SKILLS.md)
- 브랜치·배포: [`docs/BRANCHING-AND-DEPLOYMENT.md`](docs/BRANCHING-AND-DEPLOYMENT.md)

## 개발 및 검증

Python 3.13과 uv를 사용합니다. `uv sync --frozen`으로 잠금 파일대로 설치합니다.
문서 도구는 `npm ci --ignore-scripts`로 설치하고 서버 이미지에는 포함하지 않습니다.

```sh
uv run ruff check .
uv run ruff format --check .
uv run mypy src
uv run pytest
npm run lint:md
```

필수 검사는 마지막 변경 이후 실행합니다. 실제 기관 API, Claude 원격 연결, 배포 검증은 별도로 보고합니다.
DB는 도입하지 않고 공개 API 데이터만 메모리 캐시로 처리합니다. 교사 본문·초안은 저장·로그 기록하지 않습니다.
공개 MCP는 로그인·사용자 토큰 없이 URL로 연결합니다. 기관 API 키는 선택 기능을 위한 서버 비밀값이며 사용자에게 전달하지 않습니다.
원문 파일에는 자동 포맷을 적용하지 않습니다.

프로젝트 스킬 `check-project`의 원본은 `.agents/skills/check-project/SKILL.md`입니다.
Claude 진입점은 같은 파일을 가리키는 `.claude/skills/check-project` 링크입니다.

## 작업 보고

작업 결과에는 변경 내용, 실행한 검증, 미검증 영역과 위험을 간단히 적습니다.

<!-- markdownlint-disable MD034 -->

## Deploy Configuration

- Platform: vercel
- Production URL: https://korean-lit-mcp.vercel.app
- Deploy workflow: auto-deploy on push to main
- Deploy status command: npx --yes vercel@65.9.0 inspect https://korean-lit-mcp.vercel.app --json
- Merge method: squash
- Release merge method: merge
- Project type: API
- Post-deploy health check: https://korean-lit-mcp.vercel.app/health

### Custom deploy hooks

- Pre-merge: none
- Deploy trigger: automatic on push to main
- Deploy status: npx --yes vercel@65.9.0 inspect https://korean-lit-mcp.vercel.app --json
- Health check: https://korean-lit-mcp.vercel.app/health

<!-- markdownlint-enable MD034 -->

작업 PR은 `develop`으로 squash 병합하고, `develop` → `main` 릴리스는 merge commit을 사용합니다. 배포의 Git SHA가 실제 `main` 커밋과 같은지 확인합니다. 헬스체크 후 `TEST_MCP_URL=https://korean-lit-mcp.vercel.app/mcp uv run pytest tests/test_http_live.py`로 실제 도구 호출도 확인합니다. Vercel의 메모리 캐시·호출 제한은 인스턴스마다 별개입니다.
