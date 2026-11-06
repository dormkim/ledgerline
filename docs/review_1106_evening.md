# 두 번째 리뷰 (2026-11-06 저녁, 처음 보는 심사위원 5분 기준)

대상: 커밋 `f0f885f` 기준 코드·README·`docs/slides.pdf`·`docs/demo_script.md`·`eval/`. 앞 리뷰(`review_1106.md`)의 결론은 보지 않고 새로 읽었다.
기준은 규칙 원문 네 개(각 1~5점). 점수는 추정이다. 실제 배포·영상이 없는 지금 상태 기준이고, "배포 뒤"는 체크리스트 B~D를 마친 경우다.

## 1. 점수

| 기준 | 리뷰 전 | 고친 뒤(배포 전) | 배포·영상 뒤 기대 | 근거 |
|---|---|---|---|---|
| Application of Technology | 3 | 3 | 4 | 모델을 쓰는 곳은 셋(열 제안, 예외 설명, 독촉 초안)이고 셋 다 코드가 검사한다. 구조는 좋지만 Vultr Inference로 실측한 적이 0회다. 첫 화면 배지가 LLM 꺼짐 상태에서도 "Vultr Serverless Inference"라고 써서, 로컬 스크린샷을 본 심사위원에게 오해를 줄 수 있었다(고침). |
| Presentation | 3 | 3~4 | 4 | README 첫 화면이 "세 규칙"부터 시작해 문제·대상·왜 Vultr가 흩어져 있었다. 장표 6장 아키텍처 아래 글이 잘렸다. 장표 5장 질문 화면이 옛 문구였다. 영상·데모 URL은 아직 없다. |
| Business Value | 4 | 4 | 4 | 과제 원문 "reconcile transactions, flag anomalies and manage payment follow-ups"와 그대로 겹친다. 출처 있는 시장 사실(BLS)이 있다. 수익 모델은 가설이고, 메일 발송·회계 프로그램 연동이 없어 "platform thinking"은 약하다. |
| Originality | 3~4 | 4 | 4 | "멈추고 묻는다"가 질문 하나로 끝나지 않고, 사람이 고른 답도 코드가 다시 검사한다는 점이 이번에 실제 동작이 됐다(전에는 날짜 열을 금액으로 골라도 그대로 받았다). |

## 2. 점수를 깎던 문제 (우선순위)

1. **배포 막힘 위험**: README와 스크립트가 `curl raw.githubusercontent.com/...`·`git clone`을 쓰는데 레포는 11-08까지 비공개다. 내일 VM에서 첫 줄부터 실패한다. → 폴더 복사(rsync) 경로를 스크립트·README·체크리스트에 넣었다.
2. **새 VM에서 apt 잠금**: 막 만든 Ubuntu 24.04는 처음 몇 분 unattended-upgrades가 apt를 잡고 있어 `apt-get install`이 바로 실패할 수 있다. → 잠금 대기(최대 10분), 비대화식 설정.
3. **첫 실행이 빈 키로 그대로 기동**: `.env`를 만든 뒤 멈추지 않고 키 없이 컨테이너를 띄웠다. → `.env`를 만들면 멈추고, `LLM_MODEL`이 비어 있으면(LLM_DISABLED가 아니면) 기동하지 않는다.
4. **IPv6 전용 요금제**: `api.ipify.org`가 IPv4를 못 주면 `.sslip.io` 이름이 깨진 채 진행됐다. → IPv4 확인 후 멈춤, 체크리스트에 요금제 선택 주의.
5. **`PUBLIC_HOST`를 셸에만 둠**: 나중에 `docker compose ... down/logs`를 손으로 치면 `set PUBLIC_HOST` 오류로 멈췄다(로컬에서 실제로 겪음). → `deploy/.env`에 저장(gitignore 대상), compose가 자동으로 읽는다.
6. **평가 스크립트가 공개 URL에서 중간에 죽음**: 앱은 주소당 10분 20회 제한, 평가 두 세트는 20회라 이어 돌리면 429로 예외가 나고 결과 파일이 안 남는다. → 429면 기다렸다 재시도(모두 12분, 제한 창 10분보다 길게), 다른 요청 실패는 그 케이스만 실패로 기록(시험 1개).
7. **사람 답도 검사 안 함**: 화면은 "Your answer is re-checked by code"라고 하는데 열 지정 답은 검사 없이 받았다. 날짜 열을 금액으로 고르면 모든 행이 못 읽는 행이 됐다. → LLM 제안과 같은 값 검사를 사람 답에도 적용, 안 맞으면 질문을 이유와 함께 다시 보여 준다(시험 4개).
8. **다시 실행 뒤 숫자가 늘어나 보임**: 750 동률에 답하면 예외가 8→9, 연체가 2→3으로 는다(다른 750 송장이 이제 미결이라 맞는 동작). 설명이 없어 버그처럼 보였다. → 결과 맨 위에 "Re-run with your answers: …, 고르지 않은 줄은 열려 있다" 안내.
9. **LLM 배지**: 꺼짐·미설정일 때도 "Vultr Serverless Inference"를 붙였다. → 실제로 설정됐을 때만 모델·서비스 이름, 아니면 "LLM off · template wording, same numbers".
10. **추론 모델의 잘린 `<think>`**: max_tokens에서 잘리면 생각 속 중괄호를 JSON으로 읽을 수 있었다. → 잘린 생각은 "JSON 아님"으로 처리(시험 있음). Vultr에서 추론 계열 모델을 고를 경우 대비.
11. 열 지정 질문의 예시 행이 JSON 덩어리였다 → 표로. 정적 파일에 버전 쿼리(`?v=0.2.1`)를 붙여 재배포 뒤 옛 JS가 남지 않게.

12. **재배포 뒤 옛 화면**: `/`와 `/static/*`에 캐시 지시가 없어 브라우저가 옛 `index.html`을 그대로 썼다(이번 리뷰 중 실제로 겪음, 버전 쿼리만으로는 못 막는다). 심사 직전에 고쳐 다시 올리면 심사위원이 옛 화면을 볼 수 있었다. → `Cache-Control: no-cache`(304로 싸게 재검증), 시험 1개.

## 3. 배포 리허설 (Ubuntu 24.04 컨테이너)

`ubuntu:24.04` 컨테이너에서 `deploy/vultr-setup.sh`를 세 번 실행했다(호스트 Docker 소켓 사용, `systemctl`·`ufw`만 흉내).
1회차: apt 설치, get.docker.com 설치, 폴더 복사본 인식, `.env`(600) 생성 후 멈춤(exit 0).
2회차: `LLM_MODEL` 비어 있어 멈춤(exit 1, 이유 출력).
3회차(`PUBLIC_HOST=localhost`, 가짜 키·모델): 이미지 빌드, app(healthy)·Caddy 기동, `http://`→`https://` 308, `https://localhost/healthz` 응답(`state: configured`, `vultr_inference: true`).
대기 루프가 실패로 끝난 것은 localhost가 자체 서명 인증서라서이고, 실제 VM에선 sslip.io로 공인 인증서를 받는다.
흉내 낸 부분(실제 VM에서만 확인 가능): ufw 활성화, systemd의 docker 자동 시작, Let's Encrypt 발급.
남은 위험: sslip.io는 많은 사람이 쓰는 도메인이라 Let's Encrypt 발급 한도에 걸릴 수 있다. Caddy는 실패하면 ZeroSSL로 자동 재시도한다. 2분 넘게 안 뜨면 Caddy 로그를 본다.

## 4. 공개 전 비밀 점검 (git 전체 이력, 커밋 4개)

- 키·토큰 패턴(sk-, ghp_, AKIA, xox, Bearer 긴 값, PEM, JWT, `api_key=` 긴 값): **없음**. `.env`는 한 번도 커밋되지 않았다(`.gitignore`, 추가된 파일 목록으로 확인).
- 이메일: 파일 안에는 없음. **커밋 작성자 메일은 11/6 GitHub noreply 주소로 바꿨다(이력 재작성).**
- 개인 경로: `AGENTS.md`·`docs/review_1106.md`에 `~/Desktop/gmail/contest-kit/...` 경로가 한 줄씩 있다. 비밀은 아니다.
- 한국어 내부 문서(`AGENTS.md`, `docs/review_*.md`, `docs/submit_checklist.md`)가 공개된다. 체크리스트에 상금 세금(W-8BEN) 메모가 있다. 해는 없지만 영어 심사위원에겐 잡음이다. 공개 전에 남길지 사용자가 정한다.
- `.env.example`에 DeepSeek 엔드포인트 예시 한 줄(값 없음). 문제없음.

## 5. 바뀐 것

- `deploy/vultr-setup.sh`, `deploy/list-vultr-models.sh`: 위 2~5번
- `app/columns.py`(`role_problem` 공용), `app/llm_columns.py`, `app/pipeline.py`: 사람 답 검사(7번), `answer_not_used`를 질문과 단계 기록에 남김
- `app/llm.py`: 잘린 `<think>`(10번)
- `app/static/*`, `app/main.py`(버전 0.2.1, 캐시 재검증): 8·9·11·12번
- `eval/run_eval.py`: 6번
- `README.md`: 첫 화면을 문제 → 대상 → 하는 일 → 왜 Vultr 순서로, 비공개 레포 배포 경로, IPv4 요금제, 시험 수 70
- `docs/slides.html/pdf`: 표지에 한 줄 가치, 문제 장에 "누가", 아키텍처 장에 "왜 Vultr", 잘린 글 고침, 질문 화면 새로 찍음
- `docs/demo_script.md`: 답한 뒤 안내 장면 한 줄
- `docs/submit_checklist.md`: B 단계를 실제 순서로
- 시험 65 → 72, 평가 20/20 그대로(로컬 in-process, 로컬 HTTP)

## 6. 남은 약점 (배포 뒤 할 일)

1. Vultr Inference 실측 0회. 내일 배포 뒤 평가 20건을 공개 URL로 돌리고, 모델이 JSON을 잘 못 내면 프롬프트를 조정해야 한다.
2. README 첫 화면 스크린샷과 장표 5장 근거 카드는 LLM 켠 화면으로 다시 찍어야 한다(지금 근거 카드 그림은 옛 화면, 문구 자체는 맞음).
3. 영상에 "모델이 쓴 숫자가 지워지는" 장면은 실제로 일어날 때만 넣는다.
4. 계정·메일 발송·회계 프로그램 연동 없음("platform thinking"). 로드맵에 있음, 이번엔 안 한다.
