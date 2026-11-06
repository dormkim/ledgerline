# 독립 리뷰 (2026-11-06, 처음 보는 심사위원 입장)

대상: 커밋 `9124d60` 기준 코드·README·`docs/slides.pdf`·`docs/demo_script.md`·`eval/RESULTS.md`.
심사 기준은 `~/Desktop/gmail/contest-kit/20261109_vultr-agent-rush/규칙_원문.md`의 원문 네 개(각 1~5점, 규칙서 기본값):
Application of Technology, Presentation, Business Value, Originality. 아래 점수는 추정이다.

## 1. 기준별 점수 추정

| 기준 | 리뷰 시점 | 고친 뒤(배포 전) | 근거와 약점 |
|---|---|---|---|
| Application of Technology ("how effectively the chosen model(s) are integrated") | 3 | 3 (배포·실측 뒤 4 가능) | 강점: 숫자는 코드, 문장은 모델, 문장 속 숫자를 근거와 대조해 지우는 구조가 분명하다. 약점: **Vultr Serverless Inference로 한 번도 안 돌렸다**(모델 ID 미정, 대체 엔드포인트 DeepSeek로만 실측). 모델 쓰임이 문장 쓰기·열 제안 두 곳뿐이라 "모델은 장식"으로 읽힐 수 있다. 영상에서 "모델이 쓴 문장이 근거와 안 맞아 지워지는 장면"을 실물로 보여 주지 못하면 점수가 안 오른다. |
| Presentation ("problem, solution, value in < 5 min, market analysis, revenue, future plans") | 2~3 | 3~4 | 리뷰 시점: 영상 없음, 데모 URL 없음, 시장 근거 숫자 없음, 장표가 글 위주·아키텍처가 ASCII. 고친 것: 출처 있는 시장 사실(BLS), 그림 아키텍처, 요약 카드 화면, 표지 이미지. 남은 것: 영상·URL(사용자 몫). |
| Business Value | 4 | 4 | 과제 2 원문 초점 "reconcile transactions, flag anomalies and manage payment follow-ups"와 그대로 겹친다. 약점: 과제 원문의 "Platform thinking rather than a one-off local demo"에 비해 계정·작업공간·메일 발송·회계 프로그램 연동이 없다. 수익 모델은 가설로만 적혀 있다(정직하지만 약하다). |
| Originality | 3~4 | 3~4 | "멈추고 묻는 에이전트"와 "숫자 대조로 지운 문장을 보여 준다"는 흔치 않다. 대사(reconciliation) 자체는 흔한 주제라 이 두 장면이 영상에서 분명히 보여야 점수가 난다. |

## 2. 필수 제출 요건 점검 (규칙 원문 기준)

| 요건 | 상태 |
|---|---|
| 공개 GitHub 레포, MIT | LICENSE(MIT) 있음. **원격 레포 없음**(사용자 몫) |
| Vultr VM 백엔드 배포 | 스크립트(`deploy/vultr-setup.sh`)·compose 준비됨. **계정·VM 없음** |
| Vultr 위 웹 배포, 공개 Application URL | **없음**. README의 데모 URL이 자리표시자 |
| 녹화 영상 (MP4/MOV) | 대본만 있음. **영상 없음** |
| 슬라이드 PDF | 있음(이번에 9장으로 갱신) |
| 표지 이미지 (Cover image) | 리뷰 시점 **없음** → `docs/img/cover.png` 추가 |
| README에 Vultr 서비스·아키텍처·유스케이스 설명 | 있음(이번에 그림 추가) |
| LabLab 제출 폼 (제목, 짧은/긴 설명, 태그) | **없음** → `docs/submit_checklist.md`에 초안 |

## 3. 첫 화면 30초

리뷰 시점: 첫 화면은 빈 업로드 칸 두 개였다. 가치를 보려면 "Load demo data" → "Reconcile" → 질문 답하기까지 세 번 눌러야 했고,
결과 맨 위는 단계 로그(JSON 비슷한 글)였다. 처음 보는 사람은 "몇 건 맞았고 몇 건 봐야 하나"를 바로 못 읽는다.

고친 뒤: 한 문장 가치 제안 + 샘플 고르기 + 버튼 하나("Run the sample reconciliation"). 결과 맨 위에 요약 카드 다섯 개
(자동 매칭 n/전체, 검토할 예외, 질문, 연체 송장과 금액, 통화별 순차액). `/?demo=1`로 열면 바로 실행된다(영상·심사위원용).

## 4. 버그·보안

리뷰에서 찾은 것(고침, 각 건 시험 있음):
1. **제때 낸 고객에게 독촉 초안**: 송장일 기준 7일 창만 봐서, 만기일(송장 후 30일)에 참조번호 없이 들어온 입금이 짝을 못 찾고 연체로 분류됐다. 새 영국 샘플에서 드러남(Quill & Co). 만기일이 더 가까우면 만기일부터 센다. 평가 20건 그대로 통과.
2. **평가 스크립트가 RESULTS.md를 덮어씀**: 기본 출력 `eval/results.md`가 macOS(대소문자 무시)에서 `eval/RESULTS.md`와 같은 파일. 심사위원이 README대로 재현하면 결과 문서가 지워진다. 기본 출력을 `eval/local_<set>`으로 바꿈.
3. **같은 초안을 여러 번 승인 가능**: 감사 로그에 같은 결정이 여러 줄 쌓였다. 두 번째는 409.
4. **보안 헤더 없음**: CSP·nosniff·frame-ancestors 없음, 화면이 인라인 `onclick`을 써서 CSP를 걸 수도 없었다. 이벤트 위임으로 바꾸고 엄격한 CSP를 건다. 실행 결과 응답은 `Cache-Control: no-store`.

괜찮은 것: 키는 환경변수에만 있고 `/healthz`·로그·저장에 안 나온다(시험 있음). 업로드는 2MB·1,500행 제한, 바이너리·깨진 CSV는 오류로 멈춘다. 실행 ID는 추측 불가, 목록 API 없음, 24시간 뒤 삭제. 레이트 리밋은 TCP 상대 주소 기준이라 헤더 위조로 못 피한다. 컨테이너는 비루트·읽기 전용·권한 없음.

남은 위험(안 고침, 알고 둠):
- 예외 행(거래처 이름·적요)이 외부 추론 API로 나간다. README Limits에 무엇이 나가는지 밝혀 둠.
- CSV 적요에 심은 문장(프롬프트 주입)이 독촉 메일 초안 문장에 섞일 수 있다. 숫자 대조·수수료 단어 차단·사람 승인으로 막지만, 숫자 없는 URL은 걸러지지 않는다. 메일 발송이 없어서 피해 경로는 승인한 사람이 복사하는 경우뿐.
- 레이트 리밋은 프로세스 메모리라 워커를 늘리면 나뉜다(지금은 1 워커).
- `/docs`(FastAPI 자동 문서)가 공개다. 해는 없고 심사위원에겐 오히려 도움.

## 5. 영어 문장

전반적으로 짧고 정확하다. em dash는 바깥 글에 없음(`slop_check.sh` 통과). 고친 것: 총계 표 머리글이 `bank in`/`net difference` 같은 키 이름 그대로였던 것을 사람이 읽는 이름으로. 첫 화면 문구를 기능 나열에서 "무엇을 해 주나" 한 문장으로.
남은 것: README가 길다(심사위원은 위 30줄만 읽는다고 보고 맨 위에 스크린샷과 "30초 안에 해 보기"를 둠). 철자는 영국식(normalise, recognised)으로 일관.

## 6. 핵심 약점 5개 (우선순위)

1. 배포·데모 URL·영상이 없다. 지금 상태로는 필수 요건 미달로 심사 대상이 안 될 수 있다.
2. Vultr Serverless Inference 실측이 0회다. 모델 선택·JSON 응답 품질·지연이 미지수.
3. 첫 화면에서 가치가 바로 안 보였다(→ 고침: 원클릭 샘플, 요약 카드).
4. 장표에 시장 근거·그림이 없었다(→ 고침: BLS 출처 사실, 아키텍처 그림, 표지).
5. 만기일에 낸 고객에게 독촉 초안을 만드는 실제 오류(→ 고침, 시험 추가).
