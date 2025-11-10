# 🧩 Todomon: Gamified To-Do List with Pokémon Integration

> **포켓몬과 함께 성장하는 To-Do List 앱**  
> 할 일을 완료할 때마다 포켓몬이 XP를 얻고 진화하는, **게임화된 생산성 애플리케이션**입니다.  
> Python과 Tkinter를 활용해 UI/UX, 비동기 처리, API 연동 등 **풀스택 데스크톱 앱 개발 능력**을 검증한 프로젝트입니다.

---

## 🎯 프로젝트 목표

반복적이고 지루한 할 일 관리에 **Gamification(게임화)** 개념을 적용해  
사용자의 지속적인 참여(Engagement)를 유도하는 것이 목표였습니다.  
할 일 완료 시 포켓몬이 경험치를 얻고 성장하도록 하여,  
“작은 성취가 쌓이는 즐거움”을 전달하고자 했습니다.  

---

## ⚙️ 기술 스택 (Tech Stack)

<div align="center">

| 분야 | 사용 기술 |
| :---: | :--- |
| **Language** | ![Python](https://img.shields.io/badge/Python-3776AB?style=flat&logo=python&logoColor=white) |
| **GUI / UX** | Tkinter, Pillow(PIL), tkcalendar |
| **Backend** | REST API(`requests`), JSON, MySQL |
| **Async Processing** | concurrent.futures(ThreadPoolExecutor), Callback |
| **Etc** | subprocess, Git, VSCode |

</div>

---

## 💡 핵심 기여 (My Core Contributions)

| 영역 | 기술 요소 | 기여 내용 |
| :--- | :--- | :--- |
| 🎨 **GUI / UX** | Tkinter, Responsive Design (9:16) | 창 크기에 따라 자동으로 조정되는 **반응형 레이아웃**을 직접 구현했습니다. 또한 플랫폼에 상관없이 스크롤/드래그가 동작하도록 **독립형 인터랙션 시스템**을 설계했습니다. |
| ⚙️ **비동기 처리** | ThreadPoolExecutor, Callback | PokeAPI 호출 시 **UI 멈춤 현상**을 완전히 제거하기 위해 **비동기 콜백 구조**를 설계했습니다. 결과적으로 앱 반응 속도와 안정성을 동시에 확보했습니다. |
| 🧠 **데이터 처리** | REST API, JSON I/O | 포켓몬의 **진화 체인 및 한국어 명칭**을 API에서 파싱하고, 사용자 데이터(XP, 레벨 등)를 JSON 파일에 저장·로드하도록 구조화했습니다. |
| 💫 **UX 강화** | Pillow(PIL), GIF Animation | **투명도(RGBA)** 를 유지한 이미지 처리와, **로딩 GIF 프레임 단위 애니메이션**을 직접 구현해 부드러운 피드백을 제공했습니다. |

---

## ✨ 주요 기능 (Feature Highlights)

| 카테고리 | 상세 설명 |
| :--- | :--- |
| 🧩 **XP & 진화 시스템** | 할 일 완료 시 포켓몬에게 **10 XP**가 부여되고, **100 XP** 달성 시 자동으로 진화 여부를 판별합니다. 상수 기반 구조로 확장성도 고려했습니다. |
| 🌐 **API 연동** | PokeAPI에서 포켓몬 데이터를 가져올 때 **한국어 이름**을 우선적으로 표시해 국내 사용자 친화성을 높였습니다. |
| ⚡ **캐시 초기화 로직** | `subprocess`를 통해 `generate_cache.py`를 실행, 필요한 데이터를 사전에 생성해 **앱 로딩 시간을 단축**했습니다. |
| 📅 **UI 편의 기능** | `tkcalendar`를 이용한 **마감일 선택** 기능과 직관적인 인터페이스로 사용자 접근성을 강화했습니다. |

---

## 🧰 설치 및 실행 (Setup & Run)

### 1️⃣ 환경 설정
- **Python 3.x**  
- **인터넷 연결 필수**

### 2️⃣ 의존성 설치
```bash
pip install -r requirements.txt
````

**`requirements.txt`**

```
requests
Pillow
tkcalendar
concurrent.futures
```

### 3️⃣ 프로젝트 구조

```
/Todomon/
├── todomon1.py        # 메인 실행 파일
├── generate_cache.py   # 포켓몬 ID 캐시 생성 스크립트
├── loading.gif         # 로딩 애니메이션
└── user_data/          # (자동 생성) 사용자 데이터 저장 폴더
```

### 4️⃣ 실행

```bash
python todomon1.py
```

> 💡 캐시 파일(`base_ids.json`)이 없을 경우, 앱 실행 시 자동으로 `generate_cache.py`가 실행되어 초기화됩니다.

---

## 🧩 프로젝트를 통해 배운 점

이 프로젝트를 통해 **“기능이 잘 돌아가는 코드”보다 “사용자가 만족하는 프로그램”**의 가치를 배웠습니다.
단순한 기능 구현이 아니라, **UX·성능·안정성**을 함께 고려하며 문제를 해결하는 과정에서
개발자로서의 **기술적 깊이와 사고력**을 한층 성장시킬 수 있었습니다.

---

## 🙌 앞으로의 방향 (Future Work)

* ✅ **데이터베이스 연동 강화** (SQLite → MySQL 마이그레이션)
* ✅ **UI 디자인 개선** (CustomTkinter 활용 예정)
* ✅ **진화 애니메이션 추가 및 다국어 지원**

---

## 📞 연락 및 기여 (Contact)

이 프로젝트는 저의 **개발 역량과 성장 가능성**을 보여주는 포트폴리오입니다.
코드 리뷰, 기술 피드백, 협업 제안 모두 환영합니다! 💬

📧 **Email:** [[sofia00701@gmail.com](mailto:sofia00701@gmail.com)]
🐙 **GitHub:** [[https://github.com/sofia0701](https://github.com/sofia0701)]
