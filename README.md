# korean-lit-mcp

국어 교사를 위한 한국문학 MCP입니다. 검수 판본의 원문을 가져오고, 제출한 인용을 해당 원문과 문자 단위로 대조합니다. 한국고전종합DB에서는 관련 문헌의 검색 발췌와 자료 링크를 찾습니다.

## 연결

공개 MCP URL: `https://korean-lit-mcp.vercel.app/mcp`

Claude의 원격 MCP 커넥터에 URL을 등록합니다. 사용자 회원가입·토큰·인증 헤더는 필요하지 않습니다. 기관 API 설정은 서버 운영자가 관리합니다. `main`은 Vercel production, `develop`은 다음 릴리스 통합 브랜치입니다. 이 README는 develop 기준이며, 최신 변경의 운영 반영 여부는 릴리스와 배포 상태로 확인합니다.

서버와 MCP 도구 내부의 LLM 호출은 설계에서 제외합니다. 외부 모델 API·로컬 모델·MCP sampling·다른 서비스나 프로세스를 통한 LLM 추론 위임·실패 시 LLM 대체도 사용하지 않습니다. 도구는 근거 자료 조회와 일반 코드 검증을 제공하고, 해석·문항 생성·의미 판단은 사용자가 연결한 Claude 등 클라이언트 LLM이 수행합니다. 서버 운영에 별도 LLM 키나 모델 설정은 필요하지 않습니다.

## 도구와 지원 범위

| 도구 | 하는 일 | 범위와 제한 |
| --- | --- | --- |
| `search_works` | 검수 작품·판본 검색, 선택적인 국립중앙도서관 서지 검색 | 내장 작품은 김유정 「동백꽃」·「봄·봄」 두 편. NL_API_KEY 설정 시에만 외부 서지 검색 사용. 서지는 원문 제공을 보장하지 않음 |
| `get_passage` | 검수 판본의 원문·행 주소·판본 ID·해시 조회 | 현재 내장 두 작품만 제공. TXT 물리 행은 교과서 문단과 다를 수 있음 |
| `verify_quote` | 개별 인용이나 지원 형식의 초안을 원문과 대조 | 조회한 판본·해시 또는 사용자가 제공한 본문 기준. 문학 해석·문법·문제 정답은 판정하지 않음 |
| `search_classical_text` | 고전원문·한국문집총간·한국고전총간의 본문/기사명 검색 | ITKC 검색 발췌·링크 제공. 모든 고전시가·고전소설의 전문을 제공하는 도구가 아님 |
| `lookup_grammar` | 시대별 문법 개념·별칭·예시·출처 조회 | 초기 현대 8·중세 2·근대 표기 1항목. 문장 분석·시험 정답 판정은 수행하지 않음 |

### 사용 예시

- “김유정 동백꽃의 제공 판본을 찾고 원문을 가져온 다음, 이 인용들을 검증해 줘.”
- “사미인곡을 고전원문에서 **기사명으로 먼저** 검색해 줘. 원문을 확인하지 못했으면 관련 기사와 구분해 줘.”
- “홍길동전을 **한국문집총간 본문**에서 언급한 기록을 찾아 줘.”
- “현대 국어의 주격 조사와 중세 국어의 ㅎ 받침 체언을 각각 출처와 함께 조회해 줘.”

문법 조회의 `period`는 `modern`, `middle`, `early_modern` 중 하나입니다. `term`은 100자 이하, `limit`은 기본 5·최대 10입니다. 예: `{"term":"거듭 적기","period":"early_modern"}`. 다른 시대의 자료로 자동 대체하지 않으며, 미검색은 해당 시대의 검수 항목에 없다는 뜻입니다. 합성 예시와 사전의 형태 예시를 실제 문헌 인용으로 사용하지 않습니다. 문법 데이터는 [CC BY-SA 2.0 KR](data/grammar/LICENSE.md)이며 코드의 MIT 라이선스와 구분합니다.

고전 검색 요청의 `collection`은 `classic`(고전원문), `anthology`(한국문집총간), `corpus`(한국고전총간)입니다. `target=title`은 기사명 탐색, `target=body`는 본문 언급 검색이며 기존 기본값은 `body`입니다. 한 컬렉션의 0건을 전체 자료원의 미수록으로 해석하지 않습니다.

`search_context`에는 실제 요청 검색어·필터·검색 범위·결과 상태가 나옵니다. 검수 목록의 작품·판본 수와 검색 0건을 구분하며, ITKC 발췌·기관 장애도 원문 확보로 처리하지 않습니다. 사용자가 요청한 작품과 실제 검색어가 같은지 확인하세요.

`document_author`와 호환 필드 `author`는 **검색 문헌 레코드의 저자**입니다. 작품 작가는 확인되지 않아 `work_author=null`로 표시합니다. 예컨대 사미인곡 검색에서 임하필기의 이유원이 나오더라도 정철의 작품 작가를 뜻하지 않습니다. 기사명이 같아도 해당 작품 원문임을 보장하지 않습니다.

`work_candidates`는 규원가·사미인곡·홍길동전의 검수 이칭에 대응하는 참고 정보입니다. `match_kind`로 제목 후보·본문 문자열 언급·이칭 불일치·미분류를 구분하지만 레코드의 작품 동일성은 항상 미확인입니다. 귀속 이견과 근거는 [식별 계약](docs/decisions/0004-classical-identity.md)에 기록합니다. 이 기능은 원문 제공 범위를 늘리지 않습니다.

결과는 `is_excerpt=true`, `available_text=false`인 검색 발췌입니다. 강조 마크업이 포함될 수 있고, 결과의 `record_id`를 `get_passage`의 작품 ID로 사용할 수 없습니다. 출처·판본·검사 범위 확인은 [교사 안내](docs/TEACHER-GUIDE.md)를 참고하세요.

### 원문을 찾지 못했을 때

확인한 판본을 확보하거나 교사가 제공한 본문을 `verify_quote.source_text`로 대조합니다. 누락된 옛한글을 모델 기억·추정으로 복원해 시험 지문으로 사용하지 않습니다. 클라이언트에서 자료를 작성한 뒤 인용 목록 또는 표시된 초안을 검증하고, 수정 후 재검증합니다.

검증 응답의 `reference_basis`는 `reviewed_edition` 또는 `supplied_text`입니다. 제공 문자열과의 일치는 정본 인증이 아니며, 문학 해석·정답·미제출 인용·초안 전체를 검증하지 않습니다. 클라이언트가 도구를 생략하거나 지침을 무시하는 동작을 서버가 막을 수는 없습니다. [교사 안내](docs/TEACHER-GUIDE.md)의 판정과 범위를 확인하세요.

## 로컬 실행과 운영 설정

Python 3.13과 uv를 사용합니다.

```sh
uv sync --frozen
uv run python -m korean_lit_mcp
```

로컬 MCP 주소는 `http://127.0.0.1:8000/mcp`, 헬스체크는 `/health`입니다. `.env.example`은 변수명 참고용이며 `.env` 파일은 자동으로 읽지 않습니다.

| 변수 | 용도 | 미설정 시 |
| --- | --- | --- |
| `ITKC_API_URL` | 운영자가 공식 ITKC 검색 요청 주소를 HTTPS로 설정. 사용자정보·쿼리·fragment 없는 URL만 허용. 인증키 불필요 | 고전 검색 도구 호출 시 `upstream_not_configured` 오류. 내장 도구는 동작 |
| `NL_API_KEY` | 선택적인 국립중앙도서관 서지 검색용 서버 키 | 내장 검색만 사용. 발급 키 없는 API 성공·원문 공급은 검증되지 않음 |
| `MCP_ALLOWED_HOSTS` | 로컬·배포 환경의 허용 Host | 로컬 기본 호스트 또는 Vercel 시스템 도메인 사용 |

ITKC 안내 페이지 주소나 검색어가 붙은 예시 전체 URL 대신, 공식 호출 규칙의 검색 요청 주소만 설정합니다. 잘못된 URL 설정은 서버 기동 시 거부됩니다. 호출 주소는 ITKC 코드의 기본 상수로 넣지 않습니다. 키와 교사 입력을 저장소·로그에 넣지 않습니다. 교사 제공 본문·초안은 요청 중에만 처리하며 DB에 저장하지 않습니다. 이는 MCP 서버의 정책이며 연결한 AI 서비스의 대화 보관 정책과는 별개입니다.

Vercel은 `app.py`의 ASGI 앱을 실행하며 검수 원문 파일을 배포에 포함합니다. 메모리 캐시·호출 제한은 인스턴스별로 적용됩니다. 환경변수·공개 호출 제한·배포·롤백은 [운영 안내](docs/OPERATIONS.md)를 참고하세요.

## 개발 및 검사

문서 검사에 Node.js 24를 사용하며 문서 도구는 서버 이미지에 포함하지 않습니다. 로컬 검사는 기관 키 없이 실행됩니다.

```sh
npm ci --ignore-scripts
uv run ruff check .
uv run ruff format --check .
uv run mypy src
uv run pytest
npm run lint:md
```

실제 배포 서버의 원문 조회·인용 검증은 따로 확인합니다.

```sh
TEST_MCP_URL=https://korean-lit-mcp.vercel.app/mcp uv run pytest tests/test_http_live.py
```

이 원격 검사는 ITKC 검색 성공까지 확인하지는 않습니다. 고전 검색은 `ITKC_API_URL` 설정 후 실제 도구 호출로 별도 확인합니다.

## 남은 작업

- 국립중앙도서관 키 발급 후 실제 서지·판본·원문 링크·텍스트 제공 범위 실증. key가 빈 URL은 인증 오류이며 자료 없음이 아님.
- 한국학자료센터의 무키 문헌 목록은 구운몽·홍길동젼을 찾았으나 Python HTTPS 호환성·현행 전문 API·재사용 조건이 남음. 현재 도구에 연결하지 않음.
- 문법 조회는 [초기 11개 검수 항목](data/grammar/README.md)을 제공. 수록 개념·시대별 용례 확대와 교사 감수는 후속 작업이며 문장 자동 분석은 제공하지 않음.
- 실제 교사 계정·학교 환경의 반복 사용 검증.

## 개발 문서

- [에이전트 작업 규칙](AGENTS.md), [Claude 진입점](CLAUDE.md), [스킬 운영](docs/SKILLS.md)
- [브랜치·배포 전략](docs/BRANCHING-AND-DEPLOYMENT.md), [작업 계획](docs/IMPLEMENTATION-PLAN.md), [현재 상태](docs/STATUS.md)
- [교사 사용 안내](docs/TEACHER-GUIDE.md), [운영·배포 안내](docs/OPERATIONS.md)
- [ITKC 검색 실증](docs/decisions/0002-itkc-search.md), [키 없는 원문 출처 실증](docs/decisions/0003-keyless-sources.md)
