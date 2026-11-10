# 구절 검색·편집 대조·문항 보고서 사용법

현재 develop에 추가하는 도구 계약이다. production 반영은 릴리스 기록으로 확인한다. 서버는 외부 API·LLM·DB 없이 처리하며 교사 본문·초안을 저장·로그 기록하지 않는다. 의미 검색·문학 해석·정답 타당성·정본 인증은 제공하지 않는다.

## 1. 구절에서 원문 위치 찾기

search_works에서 available_text=true인 work_id·edition_id를 선택하고 다음처럼 호출한다.

```json
{
  "work_id": "gongu-13313635",
  "edition_id": "gongu-13313635-txt-20261105",
  "query": "서른[5] 말ᄉᆞᆷ"
}
```

find_passage는 각 후보의 원문 text·location·context_text와 판본 source_hash를 반환한다. query 최대 200자, 문맥 기본 앞뒤 80코드포인트(최대 300), 결과 기본 3개(최대 5)다. 원문에서 앞 11곳까지만 확인하고 has_more로 추가 후보를 표시한다. 표기 차이 검색의 일치 원문 구간이 600자를 넘으면 omitted_oversized_matches에 생략 건수를 알린다. 후보 직렬화 예산을 적용하며 omitted_budget_matches는 예산으로 생략한 후보 수다. 문맥을 줄여 다시 조회할 수 있다. 기본 HTTP/MCP 결과는 16 KiB 예산을 검사했다. 명시적 큰 요청이나 실제 클라이언트의 출력 잘림 방지까지 보장하지 않는다.

기본 exact는 문자열 그대로 찾는다. match_mode=orthography는 NFC·공백·따옴표 비교로 후보를 찾지만 원문을 고치지 않는다. 이 모드로 찾았어도 원문과 query가 같으면 match_kind=exact이며 다르면 orthography다. 여러 위치나 표기 차이는 requires_review=true다. 유사 어휘·추정 복원은 하지 않는다. 원문에 없는 구절이거나 해당 검색 범위에서 찾지 못하면 빈 items이며 기관·작품 전체 부재를 뜻하지 않는다.

좌표 start/end는 Python 문자열의 코드포인트 단위, 0부터 시작하며 끝을 제외한다. 행 주소는 1부터 시작한다. 문맥은 코드포인트에서 잘릴 수 있으므로 문자 조합·문장 단위 완결을 보장하지 않는다. location의 원문 일치 구간을 기준으로 선택하고 필요하면 get_passage로 행 범위를 조회한다.

## 2. 편집·생략한 인용 대조

verify_excerpt의 기준 본문은 work_id·edition_id·source_hash 또는 source_text 중 하나다. 교사 본문 모드의 합성 예시는 다음과 같다.

```json
{
  "source_text": "봄[1]이 온다.",
  "segments": [{"start": 0, "end": 9, "quote": "봄이 온다."}],
  "rules": {"drop_note_markers": ["[1]"]}
}
```

segments는 원문 좌표의 오름차순·비중첩이어야 한다. 구간 사이의 원문 범위는 omissions로 표시하며 생략 적절성은 판단하지 않는다. `[…]`나 `(중략)`을 자동 파싱하지 않는다. 남긴 인용 조각을 각각 지정한다.

규칙 기본값은 모두 꺼짐이며 응답 rules에는 요청한 규칙을 그대로 표시한다. ignore_whitespace=true는 비교용 사본의 공백만 제거한다. drop_note_markers는 제거할 `[숫자 1~3자리]`를 최대 20개 명시한다. 각주라는 의미는 인증하지 않으며 임의 정규식이나 문자 삭제는 받지 않는다. 어휘·한자·옛한글·부정어를 변경하면 이 규칙만으로 일치하지 않는다.

| status | 의미 | 검토 |
| --- | --- | --- |
| exact | 지정 원문 구간과 quote가 문자 그대로 같음 | 원문 범위·출처·의도는 별도 확인 |
| edited_match | 원문은 다르지만 선언한 규칙 적용 후 비어 있지 않은 문자열이 같음 | requires_review=true, 편집 내역 확인 |
| mismatch | 선언한 규칙으로 설명되지 않는 차이 또는 비어 버린 비교 | 차이·좌표·판본 확인 후 수정·재검증 |

각 items에 original·quote·비교용 문자열·원문/인용에 대응하는 positions를 제공한다. 원본은 바꾸지 않는다. differences의 범위는 비교 문자열 기준이며 positions로 원문에 대응시킨다. removed·differences 상세는 각각 20건까지, 실제 전체 건수·잘림 여부를 별도 표시한다. 필요하면 구간을 줄여 재검토한다. 원문과 quote가 처음부터 같으면 편집 규칙과 독립적으로 exact이며, 서로 다른 문자열을 모두 삭제해 비워 버린 결과는 edited_match가 아니다.

segments 최대 10개, 각 원문 구간 최대 4000자·quote 최대 2000자, 선택 원문/quote 합계 각각 10000자다. 입력 상한의 큰 HTTP/MCP 결과는 1 MiB 이내로 검사한다. 기존 verify_quote는 이러한 편집 규칙을 적용하지 않으며 엄격한 판정 계약을 유지한다. all_raw_exact / all_match_rules는 제출한 구간만의 결과이며 생략·문항 전체 인증이 아니다.

## 3. 문항 영역별 검토 보고서

review_material의 블록 종류는 passage(지문), option(선지), explanation(해설)이다. 같은 기준 본문·규칙을 사용한다. 각 인용은 실제 블록 문자열에서 추출하므로 별도 quote 복사본은 받지 않는다.

```json
{
  "source_text": "봄[1]이 온다.",
  "rules": {"drop_note_markers": ["[1]"]},
  "blocks": [{
    "block_id": "p1",
    "kind": "passage",
    "text": "지문: 봄이 온다.",
    "citations": [{"start": 4, "end": 10, "source_start": 0, "source_end": 9}]
  }]
}
```

start/end는 블록 안 범위이고 source_start/source_end는 원문 범위다. block_id는 유일해야 하며 블록 인용은 순서대로·비중첩으로 지정한다. 원문 범위가 본문을 벗어나거나 해시가 다르면 성공 항목 없이 오류를 반환한다. 인용 없는 블록은 모두 미검증이다.

반환 items는 블록 ID·종류·인용별 비교·unverified_ranges를 포함한다. 위 예시에서는 인용은 edited_match이고 “지문: ” 범위는 미검증이다. checked_count는 지정한 인용 개수, review_required_count는 편집 일치/불일치의 검토 필요 개수다. unverified_character_count는 대조하지 않은 모든 블록 코드포인트 수다. all_submitted_raw_exact는 지정 인용만의 문자 일치이며 인용 0개일 때는 false다. 해설·선지의 의미·정답·초안 전체가 검증되었다고 표시하지 않는다.

한 블록의 여러 인용도 독립 대조다. 원문 참조 순서를 인증하지 않으므로 이어 붙인 지문은 verify_excerpt로 남긴 조각의 순서를 별도 확인한다. 여러 작품의 문항은 작품별 기준 본문을 나누어 호출한다. 최대 10블록·20인용·본문 합계 30000자·인용/대조 원문 합계 각각 10000자다. PDF/HWP 업로드·OCR·표시 없는 인용 자동 추출·보고서 파일 저장은 이번 범위에 포함하지 않는다.

## 확인 범위

합성 문장과 이용 조건을 확인한 실제 내장 판본으로 코드·HTTP/MCP 흐름을 검사한다. 학교 환경·교과서 판본 적합성·교사 편집 규칙 감수·실제 클라이언트의 도구 선택은 별도 실증이 필요하다. 기관 전사를 보존하는 검사와 정본·학술 교감 인증은 구분한다.
