# 브랜치 및 배포 전략

초기에는 `main`과 `develop` 두 개의 공유 브랜치만 운영합니다. 개인 작업은 공유 브랜치에 직접 커밋하지 않고 작업 브랜치에서 진행합니다.

## 브랜치 역할

| 브랜치 | 역할 | 배포 |
| --- | --- | --- |
| `main` | 검증이 끝난 릴리스와 운영 코드 | production |
| `develop` | 다음 릴리스를 통합하는 기본 브랜치 | staging 또는 preview |
| `feature/<name>` | 새 기능 | 없음 또는 preview |
| `fix/<name>` | 일반 버그 수정 | 없음 또는 preview |
| `docs/<name>` | 문서·작업 계획 | 없음 |
| `chore/<name>` | 개발 환경·CI·운영 설정 | 필요 시 staging |
| `hotfix/<name>` | 운영 장애·긴급 수정 | production 반영 후 `develop`에도 병합 |

`local`이라는 공용 브랜치는 만들지 않습니다. 로컬 브랜치는 개발자별 작업 브랜치이며 원격에 공유하지 않는 것이 충돌과 오해를 줄입니다.

## 변경 흐름

1. `develop`을 최신화하고 `feature/*`, `fix/*`, `docs/*`, `chore/*` 브랜치를 만듭니다.
2. 작업 브랜치에서 구현과 검증을 마칩니다.
3. 작업 브랜치 → `develop` PR을 열고 리뷰와 CI를 통과시킵니다.
4. `develop`에서 통합 검증 후 `main`으로 릴리스 PR을 엽니다.
5. `main` 병합 시 버전을 기록하고 production에 배포합니다.
6. `main`에서 발생한 긴급 수정은 `hotfix/*`로 처리한 뒤 `main`과 `develop` 양쪽에 반영합니다.

공유 브랜치에는 force-push와 직접 커밋을 허용하지 않습니다. PR은 작게 유지하고, 제목과 본문에 변경 이유·검증 결과·위험을 적습니다.

작업 브랜치 → `develop`은 PR당 하나의 변경으로 squash merge합니다. `develop` → `main` 릴리스는 merge commit으로 통합해 두 장기 브랜치의 공통 이력을 유지합니다. 릴리스 후 `main`을 `develop`에 병합해 동기화하고, hotfix도 같은 방식으로 전파합니다. 동일 수정을 별도로 cherry-pick한 뒤 다시 병합하지 않습니다. [GitHub의 PR 병합 방식](https://docs.github.com/en/pull-requests/reference/pull-request-merges)

브랜치 보호는 `main`·`develop`에 PR과 필수 검사를 요구하도록 설정합니다. 혼자 작업할 때는 작성자가 자기 PR을 승인할 수 없다는 점을 고려해 리뷰 승인 수를 필수로 고정하지 않습니다. 실제 설정 여부는 저장소에서 확인합니다.

## 배포 단계

```text
작업 브랜치 → develop → staging/preview → main → production
```

- PR 생성 또는 `develop` 병합: lint, type check, unit/integration test를 실행합니다.
- `develop` 병합: staging 또는 preview에 자동 배포하고 핵심 흐름을 확인합니다.
- `main` 병합: production 배포, 헬스체크, 로그 확인을 수행합니다.
- production 배포에는 되돌릴 수 있는 이전 버전 또는 이전 커밋 기준을 남깁니다.

현재 구현 계획은 Python FastMCP·Streamable HTTP와 GitHub Actions를 기준으로 합니다. 호스팅은 실증 후 한 곳을 선택합니다. 구체적인 작업 순서와 완료 기준은 [구현 작업 계획](IMPLEMENTATION-PLAN.md)을 따릅니다.

MVP는 SQL DB 없이 운영합니다. 공개 API 응답은 단일 프로세스의 메모리 TTL 캐시에 두고, 필요 시 검수된 원문 파일을 이미지에 포함합니다. 캐시는 재시작 시 재구축하며, 교사 제공 본문·초안은 저장하지 않습니다.

staging에서 검증한 이미지 digest와 원문 자료 버전을 production으로 승격합니다. 릴리스 병합 후 소스 내용이 검증한 후보와 일치하는지 확인합니다. 키·토큰·캐시는 환경별로 분리하고, 릴리스와 hotfix를 포함한 production 배포는 같은 환경의 다른 배포와 직렬화합니다.

## 릴리스 기준

- 필수 검증이 통과했는가
- 원문 데이터와 인용 검증 결과가 변경 의도와 일치하는가
- 환경변수와 비밀값이 저장소에 노출되지 않았는가
- 배포 후 헬스체크와 핵심 MCP 요청이 정상인가
- 롤백 기준과 담당자가 정해졌는가
