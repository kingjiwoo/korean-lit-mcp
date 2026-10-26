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

## 개발 문서

- [Claude 작업 규칙](CLAUDE.md)
- [Codex/에이전트 작업 규칙](AGENTS.md)
- [스킬 운영 체계](docs/SKILLS.md)
- [브랜치 및 배포 전략](docs/BRANCHING-AND-DEPLOYMENT.md)
- [구현 작업 계획](docs/IMPLEMENTATION-PLAN.md)
