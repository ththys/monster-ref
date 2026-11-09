# 레퍼런스 아카이브 — 인수인계 (Claude Code용)

게임 **전투 기획자**가 쓰는 개인 레퍼런스 아카이브입니다. 몬스터·PC·게임 시스템 레퍼런스를 태그로 묶어 빠르게 훑고, 시스템이 어떻게 확장되는지 구조로 봅니다. 로그인하지 않은 방문자에게는 자기소개서 페이지가 보입니다.

- 사이트: https://ththys.github.io/monster-ref/ (GitHub Pages, `main` 브랜치 루트)
- 저장소: https://github.com/ththys/monster-ref (**공개 저장소** — 이메일 등 개인정보를 커밋하지 말 것)
- Firebase 프로젝트: `monster-ref` · Cloudinary cloud: `evqhgyll` (preset `monster_ref`, Unsigned)
- 사용자는 한국어로 짧게 요청합니다. 답도 쉬운 한국어로, 기술 용어 없이.

---

## 1. 파일 구조

| 파일 | 내용 |
|---|---|
| `index.html` | **앱 전체** (약 3,000줄, HTML+CSS+JS 한 파일, 빌드 없음). 외부 로드는 Google Fonts, Firebase compat SDK 10.12.2(gstatic), JSZip 3.10.1(cdnjs, 백업 때만) |
| `config.js` | `window.REF_CONFIG` — firebase 설정, cloudinary 계정 목록(새 업로드는 **마지막** 계정), 방문자 화면 제목, editors(비워 둠) |
| `firestore.rules` | 규칙 **견본** (실제 규칙은 Firebase 콘솔에 사용자가 붙여 넣음, 관리자 이메일 2개는 콘솔에만 있음) |
| `README.md` | 처음 설정 순서 (일부 내용이 예전 기준 — 아래 검수 목록 참고) |
| `tests/smoke_test.py` | Playwright 스모크 테스트 (브라우저 저장 모드, 14개 항목) |
| `.nojekyll` | Pages가 Jekyll 처리하지 않게 |

## 2. 동작 구조

- **저장 모드 2가지**: `config.js`에 Firebase가 있으면 클라우드(Firestore + Auth), 없으면 "이 브라우저에만 저장"(localStorage). 테스트는 후자로 돌립니다.
- **로그인**: 관리자 로그인 창에서 구글 또는 이메일·비밀번호(회사망은 구글 로그인이 막혀 이메일 로그인 사용). 권한은 Firestore 규칙의 이메일 목록이 결정.
- **화면 분리**: 로그인 안 함 → 방문자 화면(자기소개서, 포트폴리오는 내용 있을 때만). 관리자 → 아카이브. 관리자가 아닌 계정은 자동 로그아웃.
- **이미지·영상**: Cloudinary Unsigned 업로드. 이미지 10MB / 영상 100MB. 표시는 640px 한 가지 크기 MP4로(변환 크레딧 절약). 10MB 넘는 움짤과 **모든 움직이는 WEBP**는 브라우저에서 영상으로 바꿔 업로드(Cloudinary가 WEBP 애니메이션을 앞부분만 남기는 문제 회피, WEBP 원본은 `media.orig`로 함께 저장). 이미 이미지로 올라간 움직이는 WEBP는 변환 없이 원본 URL로 표시.

### Firestore 데이터

| 위치 | 내용 |
|---|---|
| `monsters/{id}` | 레퍼런스 전부. `kind`: 없음=몬스터, `"pc"`, `"system"`, `"def"`(예전 공통 메모) — **규칙을 바꾸지 않으려고 한 컬렉션에 몰아넣음** |
| `site/profile` | 이름·연락처·`aboutBlocks`(자기소개서)·`portBlocks`(포트폴리오)·`archiveSort`(기본 정렬). 누구나 읽기 |
| `portfolio/{id}` | 예전 "작업물 카드" 기능용. 지금 화면에서는 안 씀 |

몬스터/PC 필드: `game, version, name, nameEn, hooks[], theme[], levels[], looks[], weapons[], systems[{name,label,note}], pcs[{name,label,note}], guide(공략), link, image|media, order, createdAt, updatedAt`
시스템 필드: `kind:"system", game, name, nameEn, media, cats[](분류, 기본 시스템만), keywords[], parents[](부모 시스템 이름, **같은 게임 안**), ext(확장 포인트), similar[], guide(설명), link`
`media`: `{cloud, rt:"image"|"video", id, fmt, anim, bytes, orig?}`

localStorage 키: `monster-ref-v1`(로컬 모드 데이터), `-defs`, `-profile`, `-works`, `-sort`, `-sysgroup`, `-nav-etc`

## 3. 화면 (주소 `#해시`)

| 해시 | 화면 |
|---|---|
| `#monsters` `#systems` `#pcs` `#timeline` | 몬스터 표 / 전투 확장 시스템별 / 대응 PC 도구별 / 패치 타임라인(간트) |
| `#pc` `#pc-systems` `#pc-counters` `#pc-timeline` | PC 레퍼런스 (마지막 칸 이름은 "대응 몬스터") |
| `#sysref` | 시스템 표 (하위 시스템 묶기 기본 켜짐, 접힘) |
| `#sysref-games` / `#sysref-cats` | 게임별(게임 → 분류) / 분류별. 기본 시스템만, 하위는 부모 안에 접힘 |
| `#sysref-tree` | 확장 구조 — **게임 하나씩**, 기본 → 1차 → 2차 확장, 계열 강조 |
| `#sysref-all` | 톺아보기 — 모든 게임을 이름으로 합쳐서 (가끔 쓰는 용도) |
| `#portfolio` `#works` | 기타(왼쪽 메뉴, 기본 접힘): 자기소개서 / 포트폴리오 편집 (글·이미지 블록 편집기) |

## 4. 사용자가 정한 규칙 (뒤집지 말 것)

1. **시스템 확장은 같은 게임 안에서만** 이어진다. 부모 선택 목록도 같은 게임의 시스템만. 다른 게임과 합쳐 보는 건 `톺아보기`에서만.
2. **시스템 레퍼런스는 독립**: 시스템 이름·영문 이름 드롭다운에는 시스템 레퍼런스에 등록한 이름만 (몬스터·PC의 시스템 이름 섞지 않음).
3. **몬스터·PC의 전투 확장 시스템에는 메모를 따로 쓰지 않는다**. 같은 `게임+이름`의 시스템 레퍼런스 내용만 보여 주고, 없으면 "시스템 레퍼런스에 추가" 버튼. (대응 PC 도구는 아직 공통 메모 방식 유지)
4. **기본 시스템 추가와 확장 시스템 추가는 다른 창**: `+ 레퍼런스 추가` = 기본(분류·키워드), 행의 `+ 확장` = 확장(부모·확장 포인트, **분류 없음**). 부모가 있으면 확장 창으로 편집.
5. **하위 시스템은 기본 접힘**.
6. 표 행에는 **편집 / 삭제**만 (시스템은 `+ 확장`도). **복사·복제는 편집 창 안에만**.
7. 게임 이름은 **드롭다운**(모든 레퍼런스에서 쓴 게임 공유) + "새 게임 직접 입력". 다른 칸은 입력 + 자동완성. 칸 아래에 칩을 깔아 두는 방식은 사용자가 거절함.
8. 시스템 레퍼런스에는 **버전 칸 없음**.
9. 방문자 화면은 **직접 쓴 글+이미지**(구글 슬라이드 아님). 섹션은 자기소개서 하나 (+ 포트폴리오 내용 있을 때만).
10. 무료로 운영: Firebase Spark, Cloudinary Free(월 25크레딧, 계정 추가로 확장), GitHub Pages.

## 5. 작업 방법

1. `git pull` → `index.html` 수정
2. 문법 확인: `node -e "const s=require('fs').readFileSync('index.html','utf8');[...s.matchAll(/<script>([\s\S]*?)<\/script>/g)].forEach(x=>new Function(x[1]));console.log('ok')"`
3. `python tests/smoke_test.py` — 새 기능은 여기에 확인 항목을 추가
4. 커밋 메시지는 한국어로 무엇이 바뀌었는지 한 줄
5. `git push` 후 Pages 배포 완료 확인: `gh api repos/ththys/monster-ref/actions/runs?per_page=1 --jq '.workflow_runs[0]|.status+" "+(.conclusion//"")'` (가끔 대기열에 오래 걸림)
6. 사용자에게: 바뀐 점을 쉬운 말로, 그리고 **Ctrl+Shift+R 강력 새로고침** 안내 (폰은 주소 끝에 `?v=숫자`)
7. Firestore 규칙이나 Cloudinary 설정이 바뀌어야 하면 사용자가 콘솔에서 직접 해야 하므로 붙여 넣을 내용을 그대로 준다

### 실수했던 곳 (조심)

- 같은 이름의 CSS 클래스 충돌: 메뉴 화살표에 `.car`를 썼다가 경력 카드 `.car`와 겹침 → 새 클래스는 검색 후 사용
- `rowHTML`에서 변수를 선언 전에 써서 저장이 조용히 실패(TDZ) → 저장 실패 토스트가 뜨면 콘솔부터
- 템플릿 리터럴 안에 폼 칸을 조건부로 넣을 때 `${조건?`…`:``}` 경계를 잘못 잘라 칸이 다른 분기로 들어감
- 창에 없는 칸을 저장하면 값이 지워짐 → `tagsOr()/textOr()`로 원래 값 유지
- `kindOf()`는 `def`를 몬스터로 보지 않도록 스냅숏에서 `def`를 먼저 걸러 냄

## 6. 작업 히스토리 (2026-11-04 ~ 11-09, 커밋 31개)

1. **시작 (11-04)**: claude.ai 아티팩트로 몬스터 레퍼런스 표(태그 필터, 호버 공략 창) → 어디서든 쓰려고 GitHub Pages 단일 파일로 이전 → Firebase(동기화) + 구글 로그인 → 이메일 로그인 추가(회사망)
2. **아카이브 확장 (11-05)**: 탭→왼쪽 메뉴, 자동완성, 복사·복제, 버전·레벨 테마·후킹 이미지(키워드), 영문 이름, PC 레퍼런스, 정렬(직접 순서 포함), 공통 시스템 메모·영문명, 공략 칸, 패치 타임라인(컨텐츠: 몬스터+대응 / 아래 전투 확장 시스템)
3. **방문자 화면 (11-05)**: 구글 슬라이드 → 카드형 포트폴리오 → 최종: 직접 쓰는 자기소개서(글·움짤 블록), 기타 메뉴에 포트폴리오 페이지
4. **입력 편의 (11-06)**: 칩 선택(거절됨) → 게임 이름만 드롭다운
5. **시스템 레퍼런스 (11-07)**: 새 종류 추가, 분류·키워드·설명, 버전 제거, 이름·영문명 드롭다운, Cloudinary 연결, WEBP 잘림 대응
6. **확장 구조 (11-09)**: 부모(여러 개)·확장 포인트·비슷한 시스템, 구조도, 같은 게임 안에서만 연결, 톺아보기 분리, 부모 선택 드롭다운, `+ 확장`, 기본/확장 창 분리, 게임별(→분류)·분류별 접힌 보기, 몬스터 시스템은 시스템 레퍼런스 연동만

## 7. 검수가 더 필요한 것

**실제 서비스로 확인 안 된 것** (테스트는 전부 브라우저 저장 모드)
- [ ] 클라우드 모드에서 시스템 레퍼런스·확장(`kind:"system"`, `parents`) 저장/불러오기
- [ ] Firebase 콘솔의 규칙이 `firestore.rules` 최신본(monsters 관리자만, portfolio, site)과 같은지
- [ ] Cloudinary 업로드 실제 동작, WEBP 8초 잘림 해결 여부 (사용자가 마지막에 "그대로"라고 했고, 그 뒤 원본 표시로 바꿨으나 확인 답 없음)
- [ ] 백업 ZIP → 복원이 시스템 레퍼런스·`def`·포트폴리오 블록까지 되는지

**정리하면 좋은 것**
- [ ] 화면에서 안 쓰는 옛 코드: 칩 선택(`renderPick`, `wirePickers`), 슬라이드·작업물 카드(`renderSlide`, `shownWorks`, `openWorkForm`), 경력기술서(`openCareerForm`), `portfolio` 컬렉션 구독
- [ ] 예전 몬스터 쪽 시스템 메모(`kind:"def"`, `cat:"systems"`)는 데이터에 남아 있고 화면에 안 보임 → 필요하면 시스템 레퍼런스 설명으로 옮기기
- [ ] `README.md`가 예전 화면 기준 (구글 로그인 버튼, data.json 등)
- [ ] `similar`(비슷한 시스템)은 이름만 저장해서 다른 게임의 같은 이름과 구분이 안 됨
- [ ] Cloudinary Unsigned preset은 설정을 아는 누구나 업로드 가능 → 가끔 미디어 목록 확인 또는 업로드 제한
- [ ] 레퍼런스 수백 개 이상에서 렌더 속도 (칩마다 `sysRefFor`가 전체를 훑음)
