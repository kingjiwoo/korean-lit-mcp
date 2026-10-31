# 첫 원문 자료 경로

2026-10-26 결정: 작은 검수 원문 묶음을 파일로 제공하고 SQL DB는 사용하지 않는다. 공개 API 응답 캐시는 별도의 프로세스 메모리에서 처리한다.

## 직접 확인한 내용

- 공유마당의 [동백꽃](https://gongu.copyright.or.kr/gongu/wrt/wrt/view.do?wrtSn=9000397&menuNo=200019), [봄·봄](https://gongu.copyright.or.kr/gongu/wrt/wrt/view.do?wrtSn=9000404&menuNo=200019) 페이지는 저작자를 김유정으로, 이용조건을 `자유이용 만료`로 표시한다.
- 두 작품의 다운로드 목록에 PDF·HWP·TXT가 있고, 공개 TXT 다운로드를 실제로 수행했다. 공유마당 메타데이터 API의 본문 제공 여부와는 별개로 확인한 경로다.
- 다운로드 경로는 `/gongu/wrt/cmmn/wrtFileDownload.do?wrtSn=<작품번호>&fileSn=3`이다. HTTP 압축 해제 후의 파일 바이트를 저장하며, 편집·정규화하지 않는다.
- TXT는 UTF-8·CRLF이고 인쇄 줄바꿈이 포함된다. 교과서와 같은 판본이라고 간주하지 않으며 물리적 행으로 주소를 부여한다.
- [국립중앙도서관 소장자료 API](https://www.nl.go.kr/NL/contents/N31101030700.do)는 키 없이 직접 요청했을 때 JSON `errorCode=010`으로 거부되었다. 인증된 검색 계약 검증에는 발급 키가 필요하다.

## 재현

파일별 해시와 권리 근거는 `data/works/*.json`에 기록했다. `uv run pytest tests/test_sources.py`로 자료 무결성·권리 차단·경로와 크기 제한을 확인한다.

원문 자료 갱신은 요청 처리 중 수행하지 않는다. 새 판본을 검수한 뒤 파일·메타데이터·이미지를 함께 배포한다. 제공 파일 자체의 오탈자와 교과서 판본 차이를 자동으로 고치지 않는다.

## 남은 실증

기관 API 키를 사용한 검색 성공 응답, 교사 계정의 Claude 연결, 학교 네트워크, 호스팅과 파일럿 성공 기준은 아직 확인하지 않았다.
