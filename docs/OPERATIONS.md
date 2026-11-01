# 운영 및 배포

## 실행 조건

Python 3.13과 SQL DB 없이 운영합니다. 한 사람이 배포하면 누구나 MCP URL로 연결하는 공개 서비스입니다. Vercel Python Functions가 인스턴스를 자동 확장하므로 프로세스의 캐시·호출량은 서로 공유되지 않습니다. 공개 메타데이터만 메모리 캐시에 두며 재시작 시 사라집니다. 원문은 검수한 파일 버전과 함께 배포합니다.

| 환경변수 | 용도 |
| --- | --- |
| `MCP_ALLOWED_HOSTS` | 쉼표로 구분한 서버 호스트 이름. 생략하면 Vercel의 배포·브랜치·운영 도메인, 로컬에서는 localhost·127.0.0.1 사용 |
| `MCP_ALLOWED_ORIGINS` | 필요할 때만 브라우저 Origin을 명시적으로 허용 |
| `MCP_HOST` | 로컬 기본 127.0.0.1. 컨테이너는 0.0.0.0. Vercel에서는 사용하지 않음 |
| `PORT` | 로컬 기본 8000. 컨테이너 기본 8080. Vercel에서는 사용하지 않음 |
| `WORKS_DIR` | 검수 원문 디렉터리. 기본 data/works |
| `ITKC_API_URL` | 선택. 한국고전종합DB 검색 API의 HTTPS 주소. 미설정 시 고전 검색 도구는 설정 오류 반환 |
| `NL_API_KEY` | 선택. 국립중앙도서관 외부 서지 검색 키 |

사용자 접근 토큰은 사용하지 않습니다. 이전 버전의 `MCP_AUTH_TOKEN` 설정은 이 버전에서 사용하지 않으며, 배포한 MCP는 공개 접근을 허용합니다. 선택적인 기관 키는 비밀 관리 서비스나 실행 환경에서 전달하고 이미지·Git·공개 URL에 넣지 않습니다. `.env` 자동 로딩은 하지 않습니다.

## 로컬과 컨테이너

```sh
uv sync --frozen
uv run python -m korean_lit_mcp
docker build -t korean-lit-mcp:local .
docker run --rm --read-only --tmpfs /tmp -p 127.0.0.1:8000:8080 \
  -e MCP_ALLOWED_HOSTS=localhost,127.0.0.1 korean-lit-mcp:local
```

MCP 주소는 `http://127.0.0.1:8000/mcp`, 헬스체크는 `/health`입니다. 헬스체크가 성공해도 도구 호출이 정상임을 보장하지 않으므로 두 경로를 모두 확인합니다.

컨테이너 실행 후 `TEST_MCP_URL`을 테스트 환경에 설정하고 `uv run pytest tests/test_http_live.py`를 실행하면 인증 없이 실제 HTTP로 도구 목록 → 조회 → 판본·해시 전달 → 검증을 확인합니다.

## Vercel

운영 MCP 주소는 `https://korean-lit-mcp.vercel.app/mcp`, 헬스체크는 `https://korean-lit-mcp.vercel.app/health`입니다. 프로젝트 이름은 `korean-lit-mcp`이며 GitHub 저장소에 연결했습니다. `main`은 production, 작업 브랜치는 preview로 배포합니다.

Vercel은 `app.py`의 ASGI `app`을 불러옵니다. CLI·컨테이너와 같은 환경설정 함수를 사용하고, Python 3.13·의존성은 `.python-version`·`uv.lock`으로 고정합니다. `vercel.json`은 함수 실행을 최대 60초로 제한하며 원문 파일을 포함합니다. `.vercelignore`는 로컬 환경변수·인증 파일·개발 자료의 업로드를 제외합니다.

Vercel의 시스템 환경변수 자동 노출을 켭니다. `MCP_ALLOWED_HOSTS`가 없으면 `VERCEL_URL`, `VERCEL_BRANCH_URL`, `VERCEL_PROJECT_PRODUCTION_URL`을 허용합니다. 로컬 `.env.example`의 localhost 값을 Vercel에 복사하지 않습니다. 별도로 값을 지정하면 시스템 도메인 대신 그 목록만 허용합니다. `NL_API_KEY`는 승인 후 서버 환경에만 추가하며 새 배포부터 적용됩니다.

```sh
npx --yes vercel@65.9.0 link --project korean-lit-mcp
npx --yes vercel@65.9.0 deploy --environment preview
TEST_MCP_URL=https://korean-lit-mcp.vercel.app/mcp uv run pytest tests/test_http_live.py
```

첫 Vercel 배포는 preview 명령이어도 production에 할당될 수 있습니다. 실제 `target`과 연결된 도메인을 확인합니다. Production 도메인은 일반 사용자에게 Vercel 로그인을 요구하지 않아야 합니다. Preview의 배포 보호가 켜져 있으면 별도의 테스트 접근 방법을 사용하고 이를 사용자 인증으로 설명하지 않습니다.

최종 `develop` 검증 후 `main`으로 릴리스 PR을 merge commit으로 병합합니다. Vercel Git 연동의 새 production 배포가 해당 `main` SHA인지 확인한 뒤 공개 주소로 HTTP 테스트를 실행합니다. Git 연동이 없는 배포 환경에서는 검증된 커밋을 체크아웃하고 `npx --yes vercel@65.9.0 deploy --prod`로 배포합니다. 로컬 배포가 별도 production을 만들었으면 `main` 기반 배포로 이력을 맞춥니다.

## 공개 접근과 제한

사용자는 MCP URL만 등록합니다. 계정·OAuth·사용자 키 발급 페이지는 필요하지 않습니다. 사용자 식별과 개별 접근 회수 기능은 제공하지 않습니다.

헬스체크를 제외한 HTTP 요청은 프로세스 전체에서 분당 30개, 동시 요청 8개, 요청 본문 최대 1 MiB로 제한합니다. 모든 사용자가 이 한도를 공유하므로 개인별 사용량 보장이 아닙니다. 외부 검색의 처리 중 요청도 제한하며, 같은 질의는 하나의 업스트림 요청을 공유합니다. 제한 시 재시도를 안내하고 본문을 조용히 잘라 처리하지 않습니다.

공개 배포 전 운영 플랫폼의 요청량·비용 제한을 확인하고 기관 쿼터를 관측합니다. 한 사용자의 요청이 공유 한도를 소진할 수 있습니다. 여러 프로세스·인스턴스의 메모리 상태는 공유되지 않으므로 이 설정으로 전역 쿼터나 분산 호출량을 보장하지 않습니다.

Origin이 없는 서버 간 클라이언트는 허용합니다. 브라우저가 Origin을 보낼 때는 Host·Origin 검사를 적용하며, 추가 허용 Origin은 실제 필요한 주소만 설정합니다. 기본값이 비어 있다고 모든 브라우저 Origin을 허용하는 것은 아닙니다. Host·Origin 검사는 사용자 인증이나 비공개 접근 제어를 대신하지 않습니다.

## 로그와 외부 장애

요청 로그에는 상태·지연 등 내용 없는 지표만 남깁니다. 교사 본문·초안·인용과 비밀값을 기록하지 않습니다. FastMCP와 HTTP 라이브러리의 상세 로그는 운영 중 제한하고 외부 오류 추적·프록시에도 본문 수집을 켜지 않습니다.

기관 오류·인증 오류·쿼터 제한은 빈 성공 결과로 바꾸지 않습니다. 유효한 메타데이터 캐시가 있으면 조회 시각을 유지해 반환합니다. 외부 서지 검색이 실패해도 검수 원문 검색이 성공했다면 해당 결과와 외부 장애 안내를 반환합니다.

국립중앙도서관의 키 없는 오류 응답은 직접 확인했습니다. 인증된 검색 성공 응답은 발급 키로 별도 계약 검증이 필요합니다. 현재 XML fixture는 문서 필드를 사용한 합성 자료이며 실제 성공 응답이라고 표시하지 않습니다.

## 배포와 롤백

호스팅 계정·서비스·예산을 정하고 실제 Claude 계정에서 로그인 없는 연결을 검증합니다. 컨테이너는 비루트 사용자로 실행하고 비밀값을 빌드 시 주입하지 않습니다.

Vercel에서는 검증한 소스와 잠금 파일·원문 버전으로 `main`을 배포하고 deployment ID·Git SHA를 기록합니다. 컨테이너 배포를 사용하는 환경에서는 검증한 이미지 digest를 승격합니다. 기관 키는 환경마다 분리하고 배포는 환경별로 직렬화합니다.

배포 후 `/health`, 무인증 세 도구 목록·원문 조회·검증 성공, 잘못된 Host·Origin 거부와 입력·호출 제한을 확인합니다. 실패하면 확인된 이전 Vercel production 배포와 환경 설정으로 롤백하고 핵심 호출을 다시 확인합니다. 컨테이너는 이전 이미지 digest로 되돌립니다. 인증이 있던 버전으로 롤백하면 사용자 연결에 다시 토큰이 필요할 수 있습니다. DB 마이그레이션은 없습니다.

Vercel 인스턴스 메모리와 임시 파일의 영속성에 의존하지 않습니다. 원문 파일은 빌드 산출물에 포함하고 교사 입력·초안은 계속 저장하지 않습니다.

한국고전 검색을 활성화하려면 운영자가 `ITKC_API_URL`에 공식 호출 규칙의 검색 요청 URL을 HTTPS로 설정합니다. 코드에는 호출 주소 기본값을 두지 않습니다. `.env` 자동 로딩은 하지 않습니다. 현재 작업은 develop 통합까지이며 Vercel 환경변수 설정과 production 배포는 별도입니다.
