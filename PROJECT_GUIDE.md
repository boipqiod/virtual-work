# 🇦🇺 가상 호주 스타트업 오피스 (Virtual Office) 프로젝트 가이드

이 프로젝트는 1인 개발/학습 환경에서 실제 영어권(호주) 테크 스타트업 동료들과 협업하는 듯한 시뮬레이션 환경을 구축하기 위해 만들어진 **자율형 에이전트 연동형 업무 비서 시스템**입니다.

슬랙(Slack) 채널과 깃헙(GitHub) 이슈/PR 이벤트를 감지하여 가상의 팀원 4인방이 직설적이고 Chill한 호주 테크팀 스타일로 즉각 피드백을 남깁니다.

---

## 1. 🎯 프로젝트 기획 배경 & 목표
*   **기획 배경:** 1인 개발 환경에서 부족한 코드 리뷰, 스프린트 일정 관리, 업무 방향성에 대한 피드백 환경을 구축하여 가상으로 업무 자극과 성장의 기회를 마련함.
*   **핵심 톤앤매너:** 
    *   한국식 완곡하고 지나치게 배려 넘치는 로봇 같은 AI 톤("부담 갖지 마세요", "천천히 하세요")을 원천 차단.
    *   철저하게 직설적이고, 칠(Chill)하며, 영어권 스타트업에서 쓰이는 리얼한 비즈니스 캐주얼 대화 및 호주 테크 슬랭 강제.
*   **아키텍처 제약 돌파:** 로컬 맥 환경에 로그인된 구글 코딩 에이전트 CLI(`agy -p`)를 재활용하여 파일 기반으로 상호작용하도록 설계.
*   **GitHub 단일 통합:** 복잡하고 관리가 번거로운 Jira 및 Confluence 연동을 걷어내고, **GitHub Issues**와 **GitHub Wiki**를 단일 프로젝트 관리 도구로 활용합니다.

---

## 2. 👥 가상 스타트업 팀원 페르소나 (4인방)

| 이름 | 직책 | 캐릭터 및 톤앤매너 특징 | 시그니처 캐치프레이즈 |
| :--- | :--- | :--- | :--- |
| **Sarah** | CEO | 40대 호주인 여성. 비즈니스 지표와 마일스톤에 극도로 민감함. 결단력 있고 선을 넘는 질문을 직설적으로 꽂음. | *"So, how does this move the needle?"* |
| **Liam** | PM | 30대 호주인 남성. 스프린트 일정을 담백하지만 철저하게 통제함. 금요일마다 팀 학습과 회고를 유도함. | *"Mate, is this fitting into the current sprint?"* |
| **Chloe** | Sales / Mkt | 20대 후반 호주인 여성. 평소 텐션은 높고 친절하나, 고객 반응이나 클라이언트 피드백을 전달할 때는 극도로 냉정함. | *"Love the vibe, but clients won't buy it without X."* |
| **Aiden** | Tech Lead | 30대 중반 아일랜드/호주계. 코드 퀄리티, 패키지 사이즈, 엣지 케이스, DB 연결 유실 등의 상황을 집요하게 지적함. | *"Looks fine, but what happens when the DB connection drops?"* |

---

## 3. ⚙️ 투 트랙 아키텍처 (Two-Track Architecture)

시스템은 **팔다리(프로그램 로직)**와 **머리(AI 하네스)**가 완전히 디커플링되어 있습니다. 두 영역은 오직 `agent_io/` 내의 파일(JSON/TXT) 입출력을 통해서만 소통합니다.

```text
[Track A: 프로그램 영역]                 [우체통: 파일 인터페이스]                 [Track B: AI 하네스 영역]
  - Slack 수집 (curl)         ──>      inbox/current_event.json      ──>      - Router (에이전트 선택)
  - Github 감지 (gh CLI)      <──      outbox/final_response.json    <──      - Persona (4인방 연기: 루트 설정을 자동 로드)
  - 큐 관리 및 발송 (main)
```

---

## 4. 📂 디렉토리 구조 (2-Repository 구조)

가상 오피스 실행을 위한 하네스 프로젝트(`virtual-work`)와 실제 제품 개발을 수행할 프로젝트(`actual-product`)가 분리되어 있습니다.

```text
virtual-work/ (Harness Repo)
│
├── GEMINI.md                         # [Always On] 공통 대화 톤 규칙, 자가 교정 지침
├── .agents/                          # 에이전트 페르소나 마크다운 설정 (agy 네이티브 서브에이전트)
│   ├── liam.md
│   ├── sarah.md
│   ├── aiden.md
│   └── chloe.md
│
├── .gitignore                        # 로컬 로그 및 임시 입출력 파일 제외 설정
├── .env                              # Slack API Token, Webhook URL, GITHUB_REPO, PRODUCT_REPO_PATH 등
│
├── ⚙️ app/                           # [Track A: 프로그램 소스]
│   ├── main.sh                       # 오케스트레이터 루프 (수신 -> AI 구동 -> 발송 조율)
│   ├── slack_client.sh               # cURL 기반 슬랙 최신 메시지 수집 및 중복 비교
│   ├── github_client.sh              # gh CLI 기반 깃헙 API 수신
│   ├── queue_manager.sh              # outbox JSON 파싱 및 GitHub Issue/Wiki 자동화 실행 (AI 명의 커밋)
│   ├── daily_compressor.sh           # 자정 로그 압축 요약 & 날짜별 폴더 롤오버 관리
│   └── ai_runner.py                  # [Track B 실행기] Python 기반의 에이전트 파이프라인 조율기 (로컬 실행 모드)
│
├── 📥 agent_io/                      # [파일 인터페이스 (우체통)]
│   ├── inbox/current_event.json      # 수신된 슬랙/깃헙 메시지
│   ├── outbox/final_response.json     # 발송 대기 중인 AI 답변들
│   ├── status.json                   # last_ts 및 시스템 현재 동작 상태
│   └── memory/                       # 대화 히스토리 및 영구 맥락 보관소
│       ├── global_context.md         # 프로젝트 불변 기본 정보
│       └── YYYY-MM-DD/               # 날짜별 로그 폴더
│
└── 📜 config_harness/                # [기타 프롬프트 관리 파일]
    └── subagent_prompts/
        ├── router.txt                # 라우터: "어떤 페르소나들이 답변해야 하는가?"
        └── validator.txt             # 검증자 (현재 페르소나 자체 검증 스킬로 대체되어 미사용)
```

---

## 5. 🧠 핵심 구현 세부 스펙

### 1) AI 러너 파이프라인 (`app/ai_runner.py`)
*   **라우팅 (Stage 1):** `router.txt`를 읽고 유저의 멘트를 해석하여 `["Aiden", "Liam"]` 등 최적의 답변자를 선정해 JSON으로 반환합니다.
*   **성격 연기 (Stage 2):** 워크스페이스 로컬 루트에서 에이전트 CLI(`agy`)를 실행하며, `@liam` 등 에이전트 멘션을 전달합니다. `agy`가 루트의 `GEMINI.md`와 `.agents/` 설정을 자동으로 읽어들여 페르소나 답변을 작성합니다.

### 2) 로컬 직접 실행 설계 (Zero Sync)
*   이전 모노레포 구조와 달리 하네스 폴더 내에는 `node_modules`나 복잡한 소스코드가 없으므로, 설정 수정 시 별도의 동기화 단계(`sync_configs.sh`) 없이 **로컬 워크스페이스의 환경에서 즉시 `agy`를 구동**하여 실시간으로 수정 사항이 에이전트에 반영됩니다.

### 3) GitHub 자동화 연동 스펙
*   **GitHub Wiki 문서 생성 (`[WIKI_WRITE: Page Title]`):**
    *   에이전트가 문서를 작성하면 `queue_manager.sh`가 `WIKI_REPO_URL` 위키 저장소를 임시 폴더에 풀(Pull) 받아 문서를 작성합니다.
    *   이후 Git 커밋 시 에이전트 고유의 이름과 이메일(`-c user.name/email`)을 지정하여 커밋을 생성하고 위키에 푸시합니다.
*   **GitHub Issue 생성 (`[ISSUE_CREATE: Summary | Description]`):**
    *   이슈 요청 발생 시 로컬에 권한이 연결된 GitHub CLI(`gh`)를 호출하여 제품 개발 레포에 즉시 이슈를 생성합니다.
    *   이슈 생성 완료 후 발행된 GitHub URL을 파싱하여 본문의 태그 영역을 마크다운 링크로 깔끔하게 치환합니다.

---

## 6. 📅 메모리 요약 & 토큰 절약 전략 (Memory Compression)
시간이 흐를수록 대화 로그가 누적되면 AI가 읽을 양이 많아져서 성능 저하 및 API 비용 상승을 유발합니다. 이를 위해 **"단기 원본 + 장기 요약"** 하이브리드 메모리 롤오버 스키마를 구현했습니다.

1.  **일중 처리:** 하루 동안 발생하는 대화는 `raw_history.jsonl`에만 가볍게 누적됩니다.
2.  **자정 요약 (`app/daily_compressor.sh`):** 매일 밤 12시 크론잡이 돌아가며 오늘 하루의 전체 대화 히스토리를 AI에게 던져 핵심적인 마일스톤 변동 사항, 프로젝트 진척도만 단 **3줄 요약**하게 한 뒤 `daily_summary.md`에 쓰고 오늘 대화방은 아카이브 처리합니다.
3.  **결과:** 에이전트들은 매번 대답할 때 **"프로젝트 전체 목표(`global_context.md`) + 어제의 3줄 요약(`daily_summary.md`) + 오늘의 대화 원본"**만 결합해서 읽기 때문에, 1년 내내 대화를 진행해도 한 번에 사용하는 토큰량이 항상 최소 수준으로 고정됩니다.

---

## 7. 🚀 실행 및 연동 방법

### 1) 환경 변수 설정
`virtual-work/.env` 파일을 작성합니다.
```ini
SLACK_BOT_TOKEN=xoxb-your-bot-token        # OAuth & Permissions 에서 발급 (channels:history, channels:read 권한 필수)
SLACK_CHANNEL_ID=C0B6PFVFG8N              # 봇을 초대하여 상호작용할 슬랙 채널 ID
SLACK_WEBHOOK_URL=https://hooks.slack...   # Incoming Webhooks 에서 채널 지정 후 발급받은 발신 URL
GITHUB_REPO=your-github-username/repo-name
WIKI_REPO_URL=https://github.com/your-github-username/repo-name.wiki.git
PRODUCT_REPO_PATH=/absolute/path/to/your/actual-product-repo
LOOP_INTERVAL=10                          # 슬랙 모니터링 주기 (초 단위)
```

### 2) 실행 방법
*   **대시보드 실행:** 
    ```bash
    python3 app/dashboard.py
    ```
    브라우저에서 `http://localhost:8000`에 접속하여 실시간 대화 기록, 프롬프트 편집, 수동 스크립트 실행 대시보드를 사용할 수 있습니다.
*   **백그라운드 스케줄 크론 등록 (`crontab -e`):**
    ```bash
    # 5분 주기로 메시지 수신 및 발송 처리
    */5 * * * * cd /path/to/virtual-work && ./app/main.sh > /dev/null 2>&1
    
    # 매일 자정 로그 압축 요약 & 폴더 변경
    0 0 * * * cd /path/to/virtual-work && ./app/daily_compressor.sh > /dev/null 2>&1
    ```
