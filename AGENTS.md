# Ledgerline (Vultr Agent Rush 2026) 작업 규칙

- 대회 규칙 원문·결정: `~/Desktop/gmail/contest-kit/20261109_vultr-agent-rush/`(규칙_원문.md, 착수.md, 결정.md). 마감 2026-11-09(월) 08:00 KST.
- 과제 2(Powering the Future of Work, Finance & Accounting). 필수: Vultr VM 백엔드 + Vultr 위 웹 배포. LLM은 Vultr Serverless Inference(OpenAI 호환)를 기본으로 쓴다.
- 숫자는 코드가 계산한다(Decimal, 반올림 금지). LLM은 문장만 쓰고, 문장 속 숫자는 `app/numcheck.py`가 근거와 대조한다.
- 모르면 묻는다: 동률 후보·열 불명·일/월 순서 불명은 질문으로 멈춘다. 실패를 빈 결과로 바꾸지 않는다.
- 평가 케이스(`eval/cases`, `eval/holdout`)는 코드를 안 본 에이전트가 썼다. 새 케이스도 같은 방식으로 받고, 처음 점수를 `eval/RESULTS.md`에 먼저 적은 뒤 고친다.
- 키는 `.env`(커밋 금지)에만. `/healthz`·로그·저장 어디에도 나오면 안 된다(`tests/test_api.py`).
- 바깥 글(README, slides, 데모 대본)은 em dash 금지, 지어낸 숫자 금지, `slop_check.sh` 통과.
- 커밋은 경로 지정 add. GitHub 공개 레포 생성·Vultr 계정·제출은 사용자 몫.
