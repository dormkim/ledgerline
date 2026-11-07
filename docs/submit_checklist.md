# 제출 체크리스트 (사용자 손이 필요한 것)

마감: **2026-11-09(월) 08:00 KST** (= 11-08 23:00 UTC, 유예 5분). 목표는 **11-08(일) 22:00 KST 제출**, 마감 10시간 전.
문제가 생기면 마감 전에 주최 측에 연락해야만 연장된다(규칙서 원문).
시각은 모두 KST. 각 단계 뒤의 "→ Claude"는 그 결과(URL·키 위치)만 알려 주면 이어서 처리할 수 있는 일.

## A. 오늘 11-06(금) 저녁까지: 계정

- [ ] LabLab(lablab.ai) 가입·대회 참가 신청, LabLab Discord 가입 (대회 원문: 둘 다 가입해야 참가)
- [ ] 팀 만들기(1인 팀 가능). 프로젝트 이름 `Ledgerline`
- [ ] Vultr 계정: **Vultr를 써 본 적 없는 이메일**로 가입하고 $200 크레딧 받기(대회 원문 조건). 크레딧 받는 경로는 LabLab 대회 페이지·Discord 안내를 따른다
- [ ] Vultr 콘솔 → Serverless Inference 켜고 API 키 발급. 키는 VM의 `/opt/ledgerline/.env`에만 둔다(레포·채팅에 붙여 넣지 않기)
- [x] GitHub 비공개 레포 `dormkim/ledgerline`에 푸시됨. **공개 전환은 11-08 제출 직전**(사용자 몫)

## B. 11-07(토) 오후(쿠폰 12:45 뒤): 배포

- [ ] Vultr Cloud Compute VM 만들기: Ubuntu 24.04, 1 GB 요금제로 충분, 서울 또는 가까운 지역.
      **IPv4 주소가 있는 요금제**로 고른다(IPv6만 있는 요금제는 `<ip>.sslip.io` 인증서를 못 받는다, 스크립트가 멈추고 알려 준다).
      Vultr 방화벽 그룹을 붙였다면 22·80·443을 열어 둔다(안 붙이면 할 일 없음, VM 안의 ufw는 스크립트가 연다)
- [ ] 레포가 아직 비공개라 VM에서 `curl raw.githubusercontent…`·`git clone`이 **안 된다**. 맥에서 폴더를 복사해 올린다
      (로컬 `.env`는 안 올라감):
      `cd <레포 폴더> && rsync -a --exclude .env --exclude .git ./ root@<IP>:/opt/ledgerline/`
      (`rsync`가 없다는 오류면 VM에서 `apt-get install -y rsync` 먼저)
- [ ] VM에서 `bash /opt/ledgerline/deploy/vultr-setup.sh` → Docker 설치·방화벽·`.env`(권한 600) 만들고 멈춘다
- [ ] `nano /opt/ledgerline/.env`에 `LLM_API_KEY` → `/opt/ledgerline/deploy/list-vultr-models.sh`로 모델 고르기 → `LLM_MODEL` 입력
      (모델 목록은 키 없이도 나오는 공개 주소라, 스크립트가 먼저 빈 요청으로 키를 따로 확인한다. 401이면 키를 다시 복사. 글을 만들지 않으니 크레딧은 안 든다.
      목록에는 글을 내는 모델만 나온다. 음성·그림·임베딩 모델을 `LLM_MODEL`에 넣으면 안 된다)
- [ ] `bash /opt/ledgerline/deploy/vultr-setup.sh` 다시 실행 → 빌드·기동 후 `https://<ip-대시>.sslip.io/healthz`가 응답할 때까지 기다렸다가 출력한다.
      `"state":"configured"`, `"vultr_inference":true`인지 확인. 2분 넘게 안 뜨면 출력된 `docker compose … logs` 명령으로 Caddy 인증서 오류를 본다
- [ ] 코드를 고친 뒤 다시 올릴 때도 같은 `rsync` + `vultr-setup.sh`(공개 뒤엔 `git pull`이 자동)
- [ ] 위 URL을 Claude에게 알려 주기 → Claude:
  - 평가 20건을 공개 URL로 실행(`eval.run_eval --url`)해 Vultr Inference 실측치로 `eval/RESULTS.md`·README·장표 숫자 갱신
    (공개 앱은 주소당 10분에 20회 제한이라 두 세트를 이어 돌리면 429가 난다. 평가 스크립트가 기다렸다 다시 보낸다, 최대 12분 더 걸림)
  - 모델이 JSON을 잘 못 내면 프롬프트·파서 조정
  - LLM 켠 상태로 `docs/img/hero.png`·`shot_summary.png`·표지 다시 찍기, 장표 PDF에 데모 URL 넣어 다시 만들기
  - README 데모 URL 자리 채우기, 커밋·푸시

## C. 11-07(토) 오후 ~ 11-08(일) 오후: 영상

- [ ] `docs/demo_script.md` 대본대로 녹화(3분 이내, MP4). **공개 Vultr URL에서** 찍고 주소창이 보이게
- [ ] 찍기 전: `/healthz` 확인, 샘플 한 번 미리 실행(첫 호출이 느릴 수 있음), 새로고침
- [ ] 꼭 들어갈 장면: 요약 카드, "The agent needs you" 질문에 답하고 다시 실행, 근거 카드(E1 Delta Freight), 독촉 초안 승인, Vultr 콘솔의 VM, `/healthz`의 `vultr_inference: true`
- [ ] 가능하면: 근거 카드에 "Removed LLM sentences"가 실제로 뜬 실행이 있으면 그 장면(지어내지 말 것, 안 뜨면 넣지 않는다)
- [ ] YouTube 일부공개(또는 LabLab이 받는 방식)로 올리고 링크를 README Video 자리에 → Claude가 커밋

## D. 11-08(일) 22:00까지: LabLab 제출

- [ ] Project title: `Ledgerline`
- [ ] Short description (초안, 고쳐 써도 됨):
      `A bank reconciliation agent on Vultr: code matches bank and ledger lines, the model explains each exception and drafts payment reminders, and every number it writes is checked. When unsure, it asks.`
- [ ] Long description: README 맨 위 두 단락 + "How this maps to the judging criteria" 표 요약을 붙여 넣기
- [ ] Tags: Finance & Accounting, Challenge 2, Vultr Cloud Compute, Vultr Serverless Inference, FastAPI, Docker
- [ ] Cover image: `docs/img/cover.png` (1280×720, LLM 켠 화면으로 다시 찍은 것이 있으면 그것)
- [ ] Video: C에서 올린 링크 또는 MP4
- [ ] Slides: `docs/slides.pdf` (B에서 URL 넣어 다시 만든 것)
- [ ] Public GitHub repository URL
- [ ] Demo application platform: Vultr / Application URL: `https://<ip-대시>.sslip.io`
- [ ] 제출 후 LabLab 프로젝트 페이지에서 링크 다섯 개(레포·앱·영상·슬라이드·표지)를 직접 눌러 확인

## E. 제출 뒤 ~ 심사 끝까지

- [ ] VM을 끄지 않는다(심사위원이 URL을 연다). 크레딧이 끝난 뒤에도 쓰려면 Billing에 결제 수단 등록(대회 원문)
- [ ] 11-09(월) 오전에 `/healthz` 한 번 확인

## 이미 된 것 (Claude, 11-06 저녁 추가)

배포 스크립트를 깨끗한 Ubuntu 24.04 컨테이너에서 끝까지 실행(systemctl·ufw만 흉내): Docker 설치, `.env` 생성 후 멈춤,
모델 비었으면 멈춤, 빌드·기동, HTTP→HTTPS 리다이렉트, `/healthz` 응답까지 확인. apt 잠금 대기·IPv4 확인·비공개 레포 복사 경로·
`PUBLIC_HOST` 저장(재부팅·수동 `docker compose` 대비) 추가. 열 지정 답도 값 검사, 다시 실행 뒤 "내가 고른 답" 안내, LLM 꺼짐 배지 정직하게,
평가 스크립트 429 재시도. 시험 65 → 72. 리뷰 `docs/review_1106_evening.md`.

## 이미 된 것 (Claude, 11-06)

코드·시험 65개·평가 20/20(로컬과 Docker HTTP 모두), Docker 이미지 로컬 빌드·실행 확인(비루트, 읽기 전용),
compose 설정 검증, 원클릭 샘플 3종·요약 카드·CSV 내보내기, 보안 헤더, README 스크린샷·아키텍처 그림,
장표 9장 PDF, 표지 이미지, 리뷰 노트 `docs/review_1106.md`.
