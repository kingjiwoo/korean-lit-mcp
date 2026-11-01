# 문법 조회 초기 출처 결정

확인일: 2026-11-01. 문법 조회 구현은 [G-01~G-04 계획](../GRAMMAR-TOOL-PLAN.md#구현-pr과-검사-기준)을 따릅니다.

## 채택한 자료

국립국어원 온용어의 우리말샘 전문 용어 텍스트를 항목별로 확인했습니다. 현대 8항목·중세 2항목·근대 표기 1항목의 정의·검토한 별칭·형태 예시만 초기 번들로 구성합니다. 각 페이지의 우리말샘 텍스트에는 CC BY-SA 2.0 KR 조건이 표시돼 있습니다. 같은 페이지의 수어·미디어에 표시된 별도 비영리·변경금지 조건과 구분하며 외부 문헌의 인용 예문은 제외합니다.

대표 출처: [주격 토](https://kli.korean.go.kr/term/trgtWord/indexTrgtWord.do?trgtWordNo=2458358), [ㅎ 받침 체언](https://kli.korean.go.kr/term/trgtWord/indexTrgtWord.do?trgtWordNo=2000065), [객체 높임법](https://kli.korean.go.kr/term/trgtWord/indexTrgtWord.do?trgtWordNo=2017993), [중철](https://kli.korean.go.kr/term/trgtWord/indexTrgtWord.do?trgtWordNo=2466435). 전체 출처는 `data/grammar/entries.json`의 `sources`에 있습니다.

요약·예시 배열·시대 구분·합성 예시를 추가한 사실과 동일조건변경허락 의무를 [데이터 이용조건](../../data/grammar/LICENSE.md)에 기록했습니다. 출처 사전의 형태 예시를 실제 문헌에서 검증한 구절이라고 표시하지 않습니다. 시대의 범위는 각 개념 설명이 명시한 범위에 따르며, 근대의 중철 한 항목이 근대 문법 전반을 대표하지 않습니다.

## 이번에 사용하지 않는 경로

[한국어기초사전 OpenAPI](https://krdict.korean.go.kr/kor/openApi/openApiInfo)는 별도 키 발급이 필요하므로 런타임 조회에 연결하지 않습니다. [저작권 정책](https://krdict.korean.go.kr/kor/kboardPolicy/copyRightTermsInfo)도 텍스트의 저작자표시·동일조건변경허락과 개별 미디어 권리를 구분합니다.

기존 후보인 [제14회 국외 한국어 교원 연수 교재](https://www.korean.go.kr/front/etcData/etcDataView.do?etc_seq=216&mn_id=208)는 상세 페이지에 공공누리 제4유형(비상업·변경금지)으로 표시돼 있어 공개 서비스용 요약 번들에 포함하지 않습니다. [2018 한국 어문 규정집](https://www.korean.go.kr/front/reportData/reportDataView.do?mn_id=207&report_seq=943)은 제1유형이지만 이번 사전 개념 묶음과 별도 자료이므로 혼합하지 않습니다.

## 검증과 한계

자료 PR에서 출처·권리·시대·별칭·예시 유형을 대조하고, 조회 PR에서 스키마·ID 중복·크기·누락/잘못된 출처·이용조건·옛한글 보존을 검사합니다. 런타임은 검수 번들만 읽고 LLM 호출·API 키·영구 저장을 추가하지 않습니다. 기관 감수·교사 파일럿은 별도이며, 이 결정은 임의 문장 분석·문항 정답 보증의 근거가 아닙니다.
