import tkinter as tk
import requests
from PIL import Image, ImageTk
from io import BytesIO
import random
import threading
import concurrent.futures
from tkinter import font as tkfont
import sys
import json
import os
import subprocess
from tkinter import messagebox, font as tkfont, ttk # ttk 추가
from tkcalendar import Calendar # tkcalendar 추가
import datetime

USER_DATA_DIR = "user_data"
DATA_FILE_EXT = ".json"

# ----------------------------------------------------
# 💡 캐시 파일 존재 여부 확인 및 생성 로직 추가
# ----------------------------------------------------
CACHE_FILE = "base_ids.json"
CACHE_GENERATOR = "generate_cache.py"

if not os.path.exists(CACHE_FILE):
    print(f"[{CACHE_FILE}] 캐시 파일이 없습니다. 생성 중...")
    
    # generate_cache.py가 현재 디렉토리에 있는지 확인
    if os.path.exists(CACHE_GENERATOR):
        try:
            result = subprocess.run(
                [sys.executable, CACHE_GENERATOR],
                check=True,
                capture_output=True,
                text=True
            )
            print("캐시 파일 생성 완료.")
            
        except subprocess.CalledProcessError as e:
            print("캐시 파일 생성 중 오류 발생:")
            print(f"{e.stderr}")
            
        except FileNotFoundError:
            print(f"오류: [{CACHE_GENERATOR}] 파일을 찾을 수 없습니다. 수동으로 실행해주세요.")
            
        # 💡 [수정] else 블록 대신, 캐시 파일 생성 실패 메시지를 출력하도록 수정
        except Exception:
             print(f"캐시 생성 스크립트 파일({CACHE_GENERATOR})을 찾을 수 없거나 실행 중 예상치 못한 오류가 발생했습니다.")


# -----------------------------------------------------------
# 할 일 항목 클래스 (TaskItem)
# -----------------------------------------------------------
class TaskItem(tk.Frame):
    """체크박스와 레이블을 포함하는 단일 할 일 항목을 나타냅니다."""
    def __init__(self, parent_frame, task_name, app_instance, is_recurring=False, due_date=""):
        super().__init__(parent_frame, bg="Ivory")
        self.task_name = task_name
        self.app = app_instance
        # 💡 체크박스 상태: 기본값 False (체크되지 않음)
        self.is_completed = tk.BooleanVar(value=False) 
        self.is_recurring = is_recurring
        self.due_date = due_date
        
        self.content_frame = tk.Frame(self, bg="Ivory")
        self.content_frame.pack(fill="x", expand=True)
        
        # 💡 체크박스 위젯
        self.checkbox = tk.Checkbutton(
            self.content_frame, 
            variable=self.is_completed, 
            command=self.toggle_complete, # 클릭 시 상태 변경 함수 호출
            bg="Ivory",
            activebackground="Ivory",
            highlightthickness=0
        )
        self.checkbox.pack(side="left", padx=(0, 5))
        
        # 💡 태스크 이름 레이블 (한글 폰트 자동 적용 로직 포함)
        current_font = self.app.korean_font if self.app._is_korean(task_name) else self.app.default_font
        
        self.label = tk.Label(
            self.content_frame, 
            text=task_name, 
            bg="Ivory",
            font=current_font,
            anchor="w"
        )
        self.label.pack(side="left", fill="x", expand=True)
        
        self.info_label = tk.Label(
            self.content_frame,
            text=self._get_info_text(), # 정보 텍스트 생성
            bg="Ivory",
            fg="#e67e22", # 주황색 계열로 강조
            font=("custom_font", 10),
            anchor="e"
        )
        self.info_label.pack(side="right", padx=(5, 0))
        
        self._strikethrough_font = None
        
    def _get_info_text(self):
        info_parts = []
        if self.is_recurring:
            info_parts.append("[🔁매일반복]")
        if self.due_date:
            info_parts.append(f"[📅마감일: {self.due_date}]")
            
        return " ".join(info_parts)
        
    def toggle_complete(self):
        if self.is_completed.get():
            print(f"태스크 '{self.task_name}' 완료! (+10 XP 획득)")

            self.app.gain_xp(10)  # 경험치 10 증가
            
            self.checkbox.config(state=tk.DISABLED)
            
            # 완료된 태스크에 취소선 적용
            current_font_config = self.label.cget("font").split()
            font_name = current_font_config[0]
            font_size = int(current_font_config[1]) if len(current_font_config) > 1 else self.app.default_font[1]
            self._strikethrough_font = tkfont.Font(family=font_name, size=font_size, overstrike=1)
            self.label.config(fg="gray", font=self._strikethrough_font)
            self.info_label.config(fg="gray")
            
            # 💡 [수정] is_persistent_task 변수 할당을 TaskItem 클래스 내부에서 처리
            is_persistent_task = self.is_recurring or (self.due_date != "")
            
            if is_persistent_task: # 💡 [수정] 지역 변수 사용
                self.app._schedule_daily_reset(self)         
        else:
            pass
        
# -----------------------------------------------------------
# 경험치 계산 로직 (EvolutionXP)
# -----------------------------------------------------------
class EvolutionXP:
    """포켓몬의 진화 단계에 따라 필요한 총 경험치를 계산합니다."""
    
    BASE_XP = 100
    XP_MULTIPLIER = 1.5
    
    @staticmethod
    def get_xp_needed(evolution_stage):
        """
        주어진 진화 단계(1, 2, 3...)에서 다음 단계로 진화하기 위해 필요한 총 경험치입니다.
        """
        if evolution_stage < 1:
            return EvolutionXP.BASE_XP
        
        xp_needed = EvolutionXP.BASE_XP
        
        for _ in range(evolution_stage - 1):
            xp_needed *= EvolutionXP.XP_MULTIPLIER
            
        return int(xp_needed)
    
# ====================================================
#  ResponsiveApp 클래스
# ====================================================
class ResponsiveApp:
    """
    Tkinter 기반의 반응형 (9:16 비율) 애플리케이션 클래스입니다.
    """
    
    def __init__(self, root, aspect_ratio=(9, 16)):
        # 1. 초기 설정 및 변수 초기화
        self.current_pokemon_id = None
        self.current_pokemon_name = "미정"
        self.current_level = 1     # XP/레벨 시스템에 필요한 기본값
        self.current_xp = 0
        self.xp_needed = 100
        self.root = root
        self.aspect_ratio = aspect_ratio
        self.root.title("ToDoMonster")
        
        initial_width = 360  # 9 * 40
        initial_height = 640 # 16 * 40
        
        self.root.geometry(f"{initial_width}x{initial_height}")
        self.root.minsize(360, 640)
        
        self.base_pokemon_ids = []
        
        self.current_pokemon_id = 0
        self.evolution_chain_ids = {} # 딕셔너리로 초기화
        
        self.current_pokemon_id = 1 
        self.pokemon_image = None
        self.base_list = []
        
        self.completed_chains = {}
        
        # XP 변수
        self.current_xp = 0
        self.total_xp_needed = EvolutionXP.get_xp_needed(1)
        self.evolution_stage = 1
        
        # 💡 [수정] 스레드 풀 초기화
        self.executor = concurrent.futures.ThreadPoolExecutor(max_workers=3)
        
        self.loading_gif_frames = self._load_gif_frames("loading.gif") # loading.gif 파일이 있어야 함
        self.is_loading_gif_active = False
        self.loading_after_id = None
        
        # 💡 [수정] 이미지/GIF 변수 통합 및 초기화
        self.POKEMON_IMAGE_SIZE = (190, 190) # 포켓몬/GIF 표시 크기 고정 (프레임 200px보다 작게)
        self.LOADING_IMAGE_PATH = "loading.gif" # 로딩 GIF 파일 경로
        
        self.current_pil_image = None   # 현재 포켓몬의 PIL 이미지 원본
        self.loading_gif_frames = []    # 로딩 GIF의 PIL 프레임 목록
        self.frame_index = 0
        
        self.is_loading_gif_active = False # 로딩 애니메이션 활성 상태
        self.loading_after_id = None    # 애니메이션 루프 ID
        
        #폰트 설정
        self.default_font = ("pixelFont-7-8x14-sproutLands", 14)
        self.korean_font = ("DungGeunMo", 14)
        
        # 💡 드래그 스크롤 변수 추가
        self.last_y = 0
        
        # 2. 메인 프레임 설정
        self.main_frame = tk.Frame(root, bg="Ivory")
        root.grid_rowconfigure(0, weight=1)
        root.grid_columnconfigure(0, weight=1)
        self.main_frame.grid(row=0, column=0, sticky="nsew")
        
        # 💡 반복 설정 및 마감일 데이터 변수 초기화
        self.is_recurring = tk.BooleanVar(value=False)
        self.due_date_str = tk.StringVar(value="마감일 선택")
        
        #사용자 로그인 관리
        self.current_user = None # 현재 로그인된 사용자 이름
        self.is_logged_in = False
        
        #로그인 전 임시값
        self.xp = 0
        self.level = 1
        self.current_pokemon_id = 1
        
        self._load_user_data_if_exists() # 💡 데이터 로드 시도
        
        # 3. 위젯 생성 및 로딩 시작
        self.create_widgets()
        self.root.bind('<Configure>', self._handle_resize)
        
        # 한글 입력 감지
        self.task_entry.bind('<KeyRelease>', self._check_korean_input)
        
        # 💡 GIF 프레임 로드
        self.loading_gif_frames = self._load_gif_frames("loading.gif")
        
        # 💡 [수정] 로그인 상태가 아니면 로딩 애니메이션 시작
        if not self.is_logged_in:
            self.show_loading_animation()
        
        self.load_base_list_sync() # 미진화체 목록 동기 로드
        
        # 💡 [수정] 초기 포켓몬 로드는 로그인 성공 시로 이동
        # self._initial_load_pokemon_chain(self.current_pokemon_id) 
        
        print("미진화체 리스트 로딩 중...")
        self.update_xp_bar() # 경험치 바 초기 업데이트
        
        self.root.after(0, self._show_login_window) # 로그인 창 표시
        self.root.protocol("WM_DELETE_WINDOW", self._on_closing)
        
    def show_loading_animation(self):
        """
        로딩 GIF 애니메이션을 시작하고, self.image_label에 표시합니다.
        """
        if self.loading_gif_frames and not self.is_loading_gif_active:
            # 💡 [수정] 로딩 애니메이션 활성화 플래그 설정
            self.is_loading_gif_active = True
            self.frame_index = 0
            self._animate_loading()
        elif not self.loading_gif_frames:
            # GIF 프레임이 없을 경우 텍스트 표시
            self.image_label.config(text="포켓몬 로딩 중...", font=self.korean_font)
        
    def _stop_loading_animation(self):
        """로딩 애니메이션을 중지하고 예약된 다음 호출을 취소합니다."""
        if self.is_loading_gif_active:
            self.is_loading_gif_active = False
            # 💡 [핵심] 예약된 다음 애니메이션 호출을 취소합니다.
            if self.loading_after_id:
                self.root.after_cancel(self.loading_after_id)
                self.loading_after_id = None
            
    def _on_closing(self):
        """윈도우가 닫힐 때 사용자 데이터를 저장하고 앱을 종료합니다."""
        if self.is_logged_in:
            self.save_user_data()
        self.executor.shutdown(wait=False)
        self.root.destroy()
        sys.exit()
        
    def _handle_resize(self, event):
        """창 크기 변경 시 UI 요소들을 업데이트합니다."""
        
        # 창 너비나 높이가 변경될 때만 실행 (x, y 이동은 무시)
        if (event.widget == self.root and 
            (event.width != self.root.winfo_width() or 
             event.height != self.root.winfo_height())):
            
            # 메인 프레임의 크기를 부모 창 크기에 맞춥니다.
            self.main_frame.place(
                relx=0.5, 
                rely=0.5, 
                anchor="center", 
                relwidth=1.0, 
                relheight=1.0
            )
        
        # 💡 [수정] 이미지 크기 조절 로직 제거 (고정 크기 사용)
        
        self._configure_task_list()
        
    def _update_pokemon_display(self, pil_image):
        """
        PIL Image 객체를 받아 크기를 조정한 후 Tkinter 레이블에 표시합니다.
        
        Args:
            pil_image (Image): 표시할 PIL Image 객체.
        """
        try:
            target_size = self.POKEMON_IMAGE_SIZE
            
            # 크기 조정
            resized_image = pil_image.resize(target_size, Image.Resampling.LANCZOS)
            
            # ImageTk 객체 생성 (Tkinter가 사용할 수 있는 형식)
            self.current_tk_image = ImageTk.PhotoImage(resized_image)
            
            # 💡 [핵심] 레이블 업데이트
            self.image_label.config(image=self.current_tk_image, text="")
            self.image_label.image = self.current_tk_image # 가비지 컬렉션 방지
            
            # 💡 [추가] 로딩 완료 시 포켓몬 정보 업데이트 (선택 사항)
            # self.pokemon_info_label.config(text=f"이름: {self.current_pokemon_name}, ID: {self.current_pokemon_id}")
            
        except Exception as e:
            print(f"포켓몬 디스플레이 업데이트 중 오류 발생: {e}")
            self.image_label.config(text="이미지 표시 오류")
        
    def _configure_task_list(self):
        """
        태스크 리스트 업데이트
        """
        if hasattr(self, 'task_list_canvas') and self.task_list_canvas.winfo_exists():
            # 💡 [수정] task_canvas_frame이 정의되지 않았으므로 main_frame 너비 사용 시도
            self.root.update_idletasks()
            canvas_width = self.main_frame.winfo_width() * 0.9 # relwidth 0.9 기준
            
            if canvas_width <= 0: return

            # canvas_height = self.task_canvas_frame.winfo_height() # 높이는 relheight로 자동 조절됨
            
            # self.task_list_canvas.config(width=canvas_width, height=canvas_height) # Config 대신 itemconfigure 사용
            
            self.task_list_canvas.itemconfigure(
                "self.task_list_frame",
                width=int(canvas_width) # 정수로 변환
            )
            
            self.root.update_idletasks()
            self.task_list_canvas.config(
                scrollregion=self.task_list_canvas.bbox("all")
            )
        
    def initial_load_sequence(self):
        """앱 시작 시 초기 포켓몬 데이터와 UI를 로드합니다."""
        # (이 함수는 현재 _apply_loaded_data로 대체되어 사용되지 않음)
        pass
        
    # ------------------- GIF 로딩 및 애니메이션 -------------------
    
    def _load_gif_frames(self, filename):
        """지정된 GIF 파일에서 프레임을 로드하고 ImageTk 객체 목록으로 반환합니다."""
        
        # 💡 [필수] 이미지 크기 조정을 위해 self.POKEMON_IMAGE_SIZE 변수를 사용합니다.
        # 이 변수가 __init__에 (가로, 세로) 튜플 형태로 정의되어 있다고 가정합니다.
        try:
            target_size = self.POKEMON_IMAGE_SIZE # 예: (180, 180)
        except AttributeError:
            print("경고: POKEMON_IMAGE_SIZE가 정의되지 않았습니다. 기본값 (180, 180) 사용.")
            target_size = (180, 180) # 안전을 위한 기본값

        try:
            img = Image.open(filename)
            frames = []
            for i in range(img.n_frames):
                img.seek(i)
                
                frame = img.copy().convert("RGBA") 
                
                # 💡 [핵심 수정] 로드된 프레임의 크기를 목표 크기로 조정 (ANTIALIAS 사용)
                frame = frame.resize(target_size, Image.Resampling.LANCZOS)
                
                frames.append(ImageTk.PhotoImage(frame))
            return frames
        except FileNotFoundError:
            print(f"오류: GIF 파일 '{filename}'을 찾을 수 없습니다. 현재 디렉토리에 있는지 확인하세요.")
            return []
        except Exception as e:
            print(f"GIF 파일 로드 중 오류 발생: {e}")
            return []
            
    def _animate_loading(self):
        """GIF의 다음 프레임을 표시하고 애니메이션 루프를 예약합니다."""
        if self.is_loading_gif_active and self.loading_gif_frames:
            # 현재 프레임 인덱스 업데이트
            self.current_gif_frame_index = (self.current_gif_frame_index + 1) % len(self.loading_gif_frames)
            
            # 다음 프레임 표시
            frame = self.loading_gif_frames[self.current_gif_frame_index]
            self.image_label.config(image=frame)
            
            # 💡 [핵심] 다음 프레임을 표시하도록 50ms 후에 재귀적으로 예약
            # 이 코드가 없으면 GIF는 첫 프레임에서 멈춥니다.
            self.loading_after_id = self.root.after(50, self._animate_loading)
            
    def show_loading_animation(self):
        """로딩 애니메이션을 시작합니다."""
        if not self.is_loading_gif_active:
            self.is_loading_gif_active = True
            self.image_label.config(text="")
            self.current_gif_frame_index = -1  # 0부터 시작하도록 -1로 초기화
            
            # 💡 [핵심] 첫 프레임 표시 및 애니메이션 루프 시작
            self._animate_loading()
            
    # ------------------- API 통신 및 포켓몬 로딩 -------------------
    
    def _fetch_pokemon_data(self, pokemon_id):
        """PokeAPI에서 포켓몬 데이터와 이미지를 가져와 (이미지 객체, 이름, ID) 튜플을 반환합니다."""
        pokemon_url = f"https://pokeapi.co/api/v2/pokemon/{pokemon_id}/"
        
        try: 
            # 1. 기본 포켓몬 데이터 가져오기 (이미지 URL 포함)
            response = requests.get(pokemon_url, timeout=10)
            response.raise_for_status()
            data = response.json()
            
            # 2. 종(species) 데이터 가져오기 (한글 이름 포함)
            species_url = data['species']['url']
            species_response = requests.get(species_url, timeout=10)
            species_response.raise_for_status()
            species_data = species_response.json()
            
            # 3. 한글 이름 추출
            korean_name = next(
                (name_info['name'] for name_info in species_data['names'] if name_info['language']['name'] == 'ko'),
                data['name'].capitalize()
            )
            
            # 4. 이미지 URL 추출 (고화질 official-artwork 선호)
            image_url = data['sprites']['other'].get('official-artwork', {}).get('front_default')
            if not image_url:
                # Fallback: 일반 스프라이트
                image_url = data['sprites']['front_default']
            
            if not image_url:
                print(f"포켓몬 이미지 URL을 찾을 수 없습니다. (ID: {pokemon_id})")
                return None
                
            # 5. 이미지 다운로드
            image_response = requests.get(image_url, timeout=10)
            image_response.raise_for_status()
            
            # 6. PIL Image 객체 생성 및 RGBA로 변환 (투명도 유지)
            pil_image = Image.open(BytesIO(image_response.content)).convert("RGBA")
            
            # 7. 💡 [핵심 수정] PIL Image 객체와 필요한 정보를 튜플로 반환합니다.
            return (pil_image, korean_name, pokemon_id)
        
        except requests.exceptions.RequestException as e:
            print(f"포켓몬 데이터 로드 오류 (ID: {pokemon_id}): {e}")
            return None
        except Exception as e:
            print(f"포켓몬 데이터 처리 중 예상치 못한 오류 발생 (ID: {pokemon_id}): {e}")
            return None
        
    def _fetch_evolution_chain_url_async(self, pokemon_id):
        """진화 체인 URL 로드를 백그라운드 스레드로 예약하고 완료 시 콜백을 설정합니다."""
        # 1. 스레드풀을 사용하여 URL을 가져오는 함수를 호출합니다.
        future = self.executor.submit(self._fetch_evolution_chain_url, pokemon_id)
        
        # 2. 작업 완료 시 _check_evolution_chain_url_completion 콜백을 호출하도록 설정합니다.
        future.add_done_callback(lambda f: self.root.after(0, self._check_evolution_chain_url_completion, f))

    def _fetch_evolution_chain_url(self, pokemon_id):
        """(스레드에서 실행) 진화 체인 URL을 가져옵니다."""
        # 이 함수는 API 호출 로직을 담고, 성공 시 URL 문자열을 반환해야 합니다.
        try:
            # 예시: 포켓몬 종(species) 정보 API 호출
            species_url = f"https://pokeapi.co/api/v2/pokemon-species/{pokemon_id}"
            response = requests.get(species_url, timeout=5)
            response.raise_for_status()
            data = response.json()
            
            # 진화 체인 URL 추출
            evo_chain_url = data.get('evolution_chain', {}).get('url')
            return evo_chain_url
            
        except requests.exceptions.RequestException as e:
            print(f"진화 종 URL 로드 오류: {e}")
            return None # 실패 시 None 반환
        
    def _check_evolution_chain_url_completion(self, future):
        """진화 체인 URL 로드 완료 후 호출됩니다."""
        try:
            evo_chain_url = future.result()
            
            if evo_chain_url:
                # 💡 [핵심] URL을 인수로 사용하여 다음 단계인 데이터 로드를 시작합니다.
                self._fetch_evolution_chain_data_async(evo_chain_url)
            else:
                print("진화 체인 URL을 찾을 수 없습니다. 진화 정보 업데이트를 건너뜁니다.")
                
        except Exception as e:
            print(f"진화 체인 URL 콜백 처리 중 오류 발생: {e}")
            # 여기서 오류가 발생하여 누락된 함수를 호출했기 때문에 기존 오류가 났을 수 있습니다.

    def _fetch_evolution_chain_data_async(self, evo_chain_url):
        """진화 체인 데이터를 백그라운드 스레드로 예약합니다."""
        # 💡 self.executor가 __init__에서 concurrent.futures.ThreadPoolExecutor로 초기화되어 있어야 합니다.
        future = self.executor.submit(self._fetch_evolution_chain_data, evo_chain_url)
        future.add_done_callback(lambda f: self.root.after(0, self._check_evolution_chain_data_completion, f))

    # 💡 [해결] 실제로 누락된 함수 _fetch_evolution_chain_data를 정의합니다.
    def _fetch_evolution_chain_data(self, evo_chain_url):
        try:
            response = requests.get(evo_chain_url, timeout=5)
            response.raise_for_status()
            data = response.json()
            
            # 💡 필요한 데이터만 파싱하여 반환합니다. (여기서는 간단히 전체 데이터를 반환)
            # 실제 구현에서는 필요한 진화 단계 정보를 추출하여 반환해야 합니다.
            return data 
        except requests.exceptions.RequestException as e:
            print(f"진화 체인 데이터 로드 오류: {e}")
            return None # 실패 시 None 반환
        
    def _check_evolution_chain_data_completion(self, future):
        try:
            # 💡 진화 체인 데이터 (dict 또는 None)
            evo_data = future.result() 
            
            if evo_data:
                print("진화 체인 데이터 로드 완료. UI 업데이트 필요.")
                # 💡 여기에 진화 체인 데이터를 파싱하여 UI에 표시하는 로직을 구현해야 합니다.
                # 예: self._update_evolution_info(evo_data)
            else:
                print("진화 체인 데이터 로드 실패.")
        except Exception as e:
            print(f"진화 체인 데이터 콜백 처리 중 오류 발생: {e}")

    def _parse_evolution_chain(self, url):
        """진화 체인 URL에서 포켓몬 ID 목록을 파싱합니다."""
        try:
            response = requests.get(url, timeout=10)
            response.raise_for_status()
            chain_data = response.json()['chain']
            
            evolution_map = {}
            
            def extract_chain(chain):
                current_id = int(chain['species']['url'].split('/')[-2])
                next_evolutions = []
                
                for evo in chain['evolves_to']:
                    next_id = int(evo['species']['url'].split('/')[-2])
                    next_evolutions.append(next_id)
                    extract_chain(evo) # 재귀적으로 다음 단계 처리
                    
                if next_evolutions:
                    evolution_map[current_id] = next_evolutions
                
            extract_chain(chain_data)
            return evolution_map
        except requests.exceptions.RequestException as e:
            print(f"진화 체인 로드 오류 (URL: {url}): {e}")
            return {}

    def _initial_load_pokemon_chain(self, pokemon_id):
        """
        주어진 ID의 포켓몬 데이터를 로드하고 진화 체인을 구성합니다.
        (💡 [수정] 로딩 애니메이션을 먼저 시작합니다.)
        """
        
        if not self.is_loading_gif_active:
            self.show_loading_animation()
        
        pokemon_future = self.executor.submit(self._fetch_pokemon_data, pokemon_id)
        
        evolution_future = self.executor.submit(self._fetch_evolution_chain_url, pokemon_id)
        evolution_future.add_done_callback(self._load_evolution_chain_done)
        
        self.root.after(100, self._check_pokemon_load_completion, pokemon_future)
        
    def _load_evolution_chain_done(self, future):
        """
        [콜백 함수] 진화 체인 URL 로드가 완료된 후 호출되어 진화 정보를 로드하는
        다음 스레드 작업을 시작합니다.
        
        Args:
            future: concurrent.futures.Future 객체. 이 객체의 result()는
                    진화 체인 URL 문자열을 반환합니다.
        """
        try:
            # _fetch_evolution_chain_url의 결과(진화 체인 URL)를 가져옵니다.
            chain_url = future.result()
            
            if chain_url:
                print(f"진화 체인 URL 로드 완료: {chain_url}")
                # 💡 진화 체인 URL을 사용하여 실제 진화 정보를 로드하는 새 스레드 작업 시작
                # 이 함수(_fetch_evolution_chain_data)가 다음 포켓몬 ID 목록을 self.evolution_chain_ids에 저장해야 합니다.
                self.executor.submit(self._fetch_evolution_chain_data, chain_url)
            else:
                print("진화 체인 URL 로드 실패. (진화 체인 정보 없음)")
                # 진화 체인이 없는 포켓몬일 수 있으므로, 오류 대신 빈 리스트로 초기화합니다.
                self.evolution_chain_ids = []
                
        except Exception as e:
            # 스레드 실행 중 발생한 예외 처리
            print(f"진화 체인 URL 콜백 처리 중 오류 발생: {e}")
            self.evolution_chain_ids = []
        
    def _check_pokemon_load_completion(self, future):
        """백그라운드 포켓몬 로드 작업이 완료되었는지 확인하고 UI를 업데이트합니다."""
        if future.done():
            self._stop_loading_animation() 
            try:
                # 💡 [핵심] 스레드 작업 결과를 가져옵니다. 
                # (pil_image, name, id) 튜플을 기대합니다.
                result = future.result()
                
                # 1. 결과 유효성 및 타입 검사
                # 결과가 튜플이고, 첫 번째 요소가 'resize' 속성을 가진 Image 객체인지 확인
                if (isinstance(result, tuple) and 
                    len(result) == 3 and 
                    hasattr(result[0], 'resize')):
                    
                    pil_image, name, p_id = result
                    
                    # 2. [오류 2 해결] 다음 콜백을 위해 필수 속성 저장
                    self.current_pokemon_name = name
                    self.current_pokemon_id = p_id
                    
                    # 3. 이미지 업데이트
                    self._update_pokemon_display(pil_image)
                    
                    # 4. 정보 업데이트 (레벨 정보가 설정되어 있어야 함)
                    # self.current_level, self.current_xp, self.xp_needed가 정의되어 있다고 가정
                    self.xp_info_label.config(text=f"Lv.{self.current_level} {name} ({self.current_xp}/{self.xp_needed})")
                    
                    # 5. 진화 체인 로딩 시작 (다음 단계 콜백 호출)
                    # p_id(포켓몬 ID)를 인수로 전달하여 진화 체인 URL 로드를 시작합니다.
                    self._fetch_evolution_chain_url_async(p_id) 

                else:
                    # 데이터가 딕셔너리이거나 잘못된 형식일 때의 처리
                    self.image_label.config(text="이미지 로드 실패 (데이터 형식 오류)", font=self.korean_font)

            except Exception as e:
                # 로드 중 오류 발생 시 처리
                print(f"포켓몬 데이터 로드 중 치명적인 오류 발생: {e}")
                self.image_label.config(text="이미지 로드 실패", font=self.korean_font)
                
    def _load_pokemon_data_thread(self, pokemon_id):
        """(스레드 실행용) 포켓몬 데이터와 이미지를 로드합니다."""
        
        data = self._fetch_pokemon_data(pokemon_id)
            
        if data:
            image_url = data['sprites']['front_default']
            raw_image = self._load_pokemon_image_from_url(image_url) # PIL 이미지 반환
                
            species_url = data['species']['url']
            species_id = int(species_url.split('/')[-2])
            chain_url = self._fetch_evolution_chain_url(species_id)
                
            if chain_url:
                self.evolution_chain_ids = self._parse_evolution_chain(chain_url)
            else:
                self.evolution_chain_ids = {}
                    
            self.current_pokemon_id = pokemon_id
            self.pokemon_name = data.get('korean_name', data['name'].capitalize())
            self.pokemon_gender_rate = data.get('gender_rate', -1)
                
            # 7. 메인 스레드에서 UI 업데이트 요청
            self.root.after(0, 
                            self._update_ui_elements, 
                            raw_image,
                            self.pokemon_name, 
                            pokemon_id)
                
            print(f"포켓몬 데이터 로드 완료: {self.pokemon_name} (ID: {pokemon_id})")
        else:
            # 로드 실패 시
            self.pokemon_image = None
            self.root.after(0, self._update_ui_elements, None, "로딩 실패", 0)
            
    def _update_ui_elements(self, raw_image, pokemon_name, pokemon_id):
        """💡 [수정] 메인 스레드 콜백. 로딩을 중지하고 포켓몬 이미지를 표시합니다."""
        
        # 1. 로딩 중지
        self._stop_loading_animation() 
        
        if raw_image:
            self.current_pil_image = raw_image
            # 2. 이미지 표시 (리사이징은 _update_pokemon_display에서 처리)
            self._update_pokemon_display(raw_image) 
            # 3. 정보 업데이트
            self.update_pokemon_info(pokemon_name, pokemon_id)
        else:
            # 4. 실패 처리
            self.image_label.config(text="이미지 로드 실패", image='', width=self.POKEMON_IMAGE_SIZE[0], height=self.POKEMON_IMAGE_SIZE[1])
            self.update_pokemon_info(f"{pokemon_name} (실패)", pokemon_id)
            self.current_pil_image = None
        
    def _load_pokemon_image_from_url(self, url, size=None):
        """💡 [수정] URL에서 PIL Image 객체를 다운로드하고 고정 크기로 리사이즈합니다."""
        try:
            image_response = requests.get(url, timeout=10)
            image_response.raise_for_status()
            image_data = image_response.content
            
            image = Image.open(BytesIO(image_data))
            
            # 💡 [수정] size 인자 대신 고정 크기(POKEMON_IMAGE_SIZE) 사용
            img_width, img_height = self.POKEMON_IMAGE_SIZE
            image = image.resize((img_width, img_height), Image.Resampling.LANCZOS)
            
            return image
        except requests.exceptions.RequestException as e:
            print(f"이미지 로드 오류 (URL: {url}): {e}")
            return None
            
    def display_pokemon(self):
        """(로그인 시) 이미 로드된 포켓몬 이미지를 표시합니다."""
        if self.current_pil_image:
             self._update_pokemon_display(self.current_pil_image)
        elif self.pokemon_image: # self.pokemon_image는 PhotoImage
            self.image_label.config(image=self.pokemon_image)
            self.image_label.image = self.pokemon_image
        else:
            # 로드된 이미지가 없으면 로딩 애니메이션 시작
            self.show_loading_animation()
            
    def update_pokemon_info(self, name, id):
        """포켓몬 이름과 도감번호를 업데이트합니다 (메인 스레드에서 실행)."""
        status_text = f"이름: {name}, 도감번호: {id}"
        self.pokemon_info_label.config(text=status_text)
        
    # ------------------- XP 증가 및 진화 로직 -------------------
    def gain_xp(self, amount):
        """경험치를 증가시키고 진화/재선택 로직을 처리합니다."""
        self.current_xp += amount
        self.root.after(0, self.update_xp_bar)
        
        if self.current_xp >= self.total_xp_needed:
            self.current_xp -= self.total_xp_needed # 초과 경험치 남기기
            self.evolution_stage += 1
            self.total_xp_needed = EvolutionXP.get_xp_needed(self.evolution_stage)
            
            current_id = self.current_pokemon_id
            next_evolutions = self.evolution_chain_ids.get(current_id, [])
            
            if next_evolutions:
                new_id = next_evolutions[0] 
                messagebox.showinfo("진화!", f"{self.pokemon_name}이(가) 새로운 포켓몬으로 진화합니다!")
                self._change_pokemon(new_id)
            else:
                messagebox.showinfo("만렙!", f"{self.pokemon_name}은(는) 최종 진화 단계입니다! 새로운 포켓몬을 선택합니다.")
                self._change_pokemon_randomly()
        
        self.save_user_data()

    def _change_pokemon(self, new_id):
        """포켓몬 ID를 변경하고 새로운 포켓몬 데이터를 로드합니다."""
        self.current_pokemon_id = new_id
        self.evolution_stage = 1
        self.total_xp_needed = EvolutionXP.get_xp_needed(1)
        
        # 💡 [수정] 스레드 직접 생성 대신 _initial_load_pokemon_chain 호출
        self._initial_load_pokemon_chain(new_id)
        
    def _change_pokemon_randomly(self):
        """미진화체 목록에서 랜덤으로 새 포켓몬을 선택합니다."""
        if self.base_list:
            new_id = random.choice(self.base_list)
            self._change_pokemon(new_id)
        else:
            messagebox.showerror("오류", "미진화체 목록이 로드되지 않아 새로운 포켓몬을 선택할 수 없습니다.")
            self._change_pokemon(1) # 오류 시 기본값 1번으로 변경

    def _schedule_daily_reset(self, task_item):
        """매일 반복 태스크의 경우 다음 날 자정에 완료 상태를 해제하도록 예약합니다."""
        if not task_item.is_recurring:
            return
            
        now = datetime.datetime.now()
        tomorrow = now + datetime.timedelta(days=1)
        reset_time = datetime.datetime(tomorrow.year, tomorrow.month, tomorrow.day, 0, 0, 0)
        
        time_until_reset = (reset_time - now).total_seconds() * 1000 # 밀리초 변환
        
        print(f"'{task_item.task_name}' 태스크는 {reset_time.strftime('%Y-%m-%d %H:%M:%S')}에 초기화됩니다.")
        
        self.root.after(int(time_until_reset), self._reset_task_completion, task_item)
        
    def _reset_task_completion(self, task_item):
        """매일 반복 태스크의 완료 상태를 해제하고 UI를 초기화합니다."""
        if task_item.is_recurring:
            task_item.is_completed.set(False)
            task_item.checkbox.config(state=tk.NORMAL)
            
            task_item.label.config(fg="black", font=task_item.app.korean_font)
            task_item.info_label.config(fg="#e67e22")
            
            print(f"'{task_item.task_name}' 태스크가 초기화되었습니다.")
            
            self._schedule_daily_reset(task_item)

    # ------------------- 사용자 데이터 저장/로드 및 로그인 로직 -------------------
    
    def _get_user_filepath(self, username):
        """사용자 데이터 파일 경로를 반환합니다."""
        if not os.path.exists(USER_DATA_DIR):
            os.makedirs(USER_DATA_DIR)
        return os.path.join(USER_DATA_DIR, f"{username}{DATA_FILE_EXT}")
        
    def save_user_data(self):
        """현재 사용자의 태스크, XP, 포켓몬 현황을 파일에 저장합니다."""
        if not self.is_logged_in:
            return
        
        data = {
            "xp": self.current_xp,
            "level": self.evolution_stage,
            "current_pokemon_id": self.current_pokemon_id,
            "tasks": []
        }
        
        for widget in self.task_list_frame.winfo_children():
            if isinstance(widget, TaskItem):
                task_data = {
                    "name": widget.task_name,
                    "completed": widget.is_completed.get(),
                    "recurring": widget.is_recurring,
                    "due_date": widget.due_date
                }
                data["tasks"].append(task_data)
        
        filepath = self._get_user_filepath(self.current_user)
        
        try:
            with open(filepath, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=4)
            print(f"[{self.current_user}] 데이터 저장 완료.")
        except Exception as e:
            messagebox.showerror("저장 오류", f"사용자 데이터 저장 중 오류 발생: {e}")

    def load_base_list_sync(self):
        """미진화체 목록을 동기적으로 로드합니다. 앱 시작 시 로그인 전에 호출됩니다."""
        if os.path.exists(CACHE_FILE):
            try:
                with open(CACHE_FILE, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    
                    if isinstance(data, dict):
                        self.base_list = data.get("base_ids", [])
                    elif isinstance(data, list):
                        self.base_list = data
                    else:
                        print("경고: 캐시 파일 내용이 딕셔너리 또는 리스트가 아닙니다.")
                        self.base_list = []
                        
                    print(f"[{CACHE_FILE}] 동기 로드 완료. 미진화체 {len(self.base_list)}종.")

            except Exception as e:
                print(f"캐시 파일 로드 중 오류 발생: {e}") 
                self.base_list = [] 
                
        else:
            print("캐시 파일이 존재하지 않아 미진화체 목록 로드 실패. (generate_cache.py 확인 필요)")
            self.base_list = []

    def update_scrollregion(self):
        self.task_list_frame.update_idletasks()
        self.task_list_canvas.config(scrollregion=self.task_list_canvas.bbox("all"))
        frame_width = self.task_list_canvas.winfo_width()
        if frame_width > 0:
            self.task_list_canvas.itemconfigure(
                "self.task_list_frame", width=frame_width
            )
        self.task_list_canvas.yview_moveto(1)

    def load_user_data(self, username):
        """지정된 사용자의 데이터를 파일에서 로드합니다."""
        filepath = self._get_user_filepath(username)
        if not os.path.exists(filepath):
            return None # 파일 없음
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                data = json.load(f)
            print(f"[{username}] 데이터 로드 완료.")
            return data
        except Exception as e:
            messagebox.showerror("로드 오류", f"사용자 데이터 로드 중 오류 발생: {e}")
            return None
            
    def _load_user_data_if_exists(self):
        """앱 시작 시 마지막 로그인 사용자 데이터가 있으면 로드합니다."""
        pass # 로그인 창에서 처리
    
    def _logout_user(self):
        """현재 사용자를 로그아웃하고 모든 데이터를 저장한 후, 로그인 화면으로 돌아갑니다."""
        if self.current_user:
            #self._save_user_data(self.current_user)
            self.current_user = None
            self.is_logged_in = False
            
            # XP, 레벨 등 임시값으로 초기화
            self.xp = 0
            self.level = 1
            self.current_pokemon_id = 1
            
            # UI 초기화 (태스크 리스트, XP 바 등)
            self.clear_task_list()
            self.update_xp_bar() 
            
            # 포켓몬 이미지 초기화 및 로딩 애니메이션 다시 시작
            self.image_label.config(image='', text="로그인이 필요합니다.")
            self.show_loading_animation()
            
            # 로그인 창 다시 표시
            self.root.after(100, self._show_login_window)
            
            # 💡 [추가] 로그아웃 버튼 숨김 (로그인 창에서는 필요 없음)
            self.logout_button.place_forget()

    def _apply_loaded_data(self, data):
        """로드된 데이터를 앱의 상태에 적용합니다."""
        self.current_xp = data.get("xp", 0)
        self.evolution_stage = data.get("level", 1)
        self.total_xp_needed = EvolutionXP.get_xp_needed(self.evolution_stage)
        
        if "current_pokemon_id" in data:
            self.current_pokemon_id = data["current_pokemon_id"]
        else:
            if self.base_list:
                self.current_pokemon_id = random.choice(self.base_list) 
            else:
                self.current_pokemon_id = 1 
        
        # 💡 [수정] 포켓몬 데이터 로드 시작
        self._initial_load_pokemon_chain(self.current_pokemon_id)
        self.update_xp_bar() 

        # 기존 태스크 목록 정리
        for widget in self.task_list_frame.winfo_children():
            widget.destroy()

        # 태스크 목록 복원
        for task_data in data.get("tasks", []):
            task_item = TaskItem(
                self.task_list_frame, 
                task_data["name"], 
                self, 
                is_recurring=task_data.get("recurring", False),
                due_date=task_data.get("due_date", "")
            )
            task_item.pack(fill="x", padx=10, pady=2)
            
            if task_data.get("completed", False):
                task_item.is_completed.set(True)
                task_item.checkbox.config(state=tk.DISABLED)
                current_font_config = task_item.label.cget("font").split()
                font_name = current_font_config[0]
                font_size = int(current_font_config[1]) if len(current_font_config) > 1 else self.default_font[1]
                strikethrough_font = tkfont.Font(family=font_name, size=font_size, overstrike=1)
                task_item.label.config(fg="gray", font=strikethrough_font)
                task_item.info_label.config(fg="gray")
                
                if task_data.get("recurring", False):
                    self._schedule_daily_reset(task_item)

        self.update_scrollregion()

    def _login_or_create_user(self, username, login_window):
        """사용자로 로그인하거나 새 사용자를 생성하고 데이터를 로드합니다."""
        username = username.strip()
        if not username:
            messagebox.showerror("오류", "사용자 이름을 입력해주세요.")
            return
            
        data = self.load_user_data(username)
        
        if data is None:
            if messagebox.askyesno("새 사용자", f"'{username}' 사용자가 없습니다. 새로 생성하시겠습니까?"):
                self.current_user = username
                self.is_logged_in = True
                self._apply_loaded_data({}) # 새 사용자, 랜덤 포켓몬 할당
                messagebox.showinfo("성공", f"새 사용자 '{username}'님 환영합니다!")
            else:
                return
        else:
            # 기존 사용자 로드
            self.current_user = username
            self.is_logged_in = True
            self._apply_loaded_data(data) # 저장된 데이터 로드
            messagebox.showinfo("성공", f"'{username}'님 환영합니다! 데이터가 로드되었습니다.")
            
        # 💡 [수정] 로그인 성공 시 팝업 닫기 및 UI 업데이트
        login_window.destroy()
        
        # 💡 [수정] _stop_loading_animation은 _apply_loaded_data -> _initial_load.. -> _update_ui_elements에서 호출됨
        # self._stop_loading_animation() 
        self.display_pokemon() # 로드된 포켓몬 이미지 표시
        
        self.logout_button.place(relx=1.0, rely=0.0, x=-10, y=10, anchor="ne")
        self._show_xp_bar() 
        self.root.title(f"To Do Monster - {self.current_user}")

    def _show_login_window(self):
        """로그인 또는 사용자 생성 팝업을 표시합니다."""
        login_window = tk.Toplevel(self.root)
        login_window.title("로그인")
        login_window.geometry("300x150")
        login_window.attributes('-topmost', 'true')
        login_window.protocol("WM_DELETE_WINDOW", lambda: sys.exit()) # 팝업 닫으면 앱 종료
        
        tk.Label(login_window, text="사용자 이름:").pack(pady=(10, 0))
        
        username_entry = tk.Entry(login_window)
        username_entry.pack(pady=5, padx=20, fill="x")
        username_entry.focus_set()
        
        # 💡 [삭제] 로컬 login_action 함수 삭제 (attempt_login이 _login_or_create_user를 호출하도록)
        
        def attempt_login(event=None):
            self._login_or_create_user(username_entry.get(), login_window)
            
        login_button = tk.Button(login_window, text="로그인/생성", command=attempt_login)
        login_button.pack(pady=10)
        
        username_entry.bind('<Return>', attempt_login)
        
    def logout(self):
        """현재 사용자를 로그아웃합니다."""
        if self.is_logged_in:
            self.save_user_data() # 데이터 저장
            self.is_logged_in = False
            self.current_user = None
            self.root.title("ToDoMonster")
            self._hide_xp_bar()
            self.logout_button.place_forget()
            
            # UI 초기화 (태스크 목록 비우기)
            for widget in self.task_list_frame.winfo_children():
                widget.destroy()
            self.task_entry.delete(0, tk.END)
            
            # 💡 [수정] 포켓몬 이미지 로딩 애니메이션 다시 시작
            self.show_loading_animation() 
            self.pokemon_info_label.config(text="이름: ?, 도감번호: ?")
            
            self._show_login_window()
            
    # ------------------- 유틸리티 -------------------
    
    def _is_korean(self, text):
        """주어진 텍스트에 한글 문자가 포함되어 있는지 확인합니다."""
        if not text: return False
        # 한글 유니코드 범위: 가(0xAC00) ~ 힣(0xD7A3)
        for char in text:
            if 0xAC00 <= ord(char) <= 0xD7A3:
                return True
        return False
        
    def _check_korean_input(self, event):
        """ 키 입력이 해제될 때마다 입력된 텍스트를 확인하고 폰트를 변경합니다. """
        current_text = self.task_entry.get()
        current_font_name = self.task_entry.cget("font").split()[0]
        korean_font_name = self.korean_font[0]
        default_font_name = self.default_font[0]
        
        # 입력 박스 폰트 크기는 고정 24 사용
        if self._is_korean(current_text) and current_font_name != korean_font_name:
            self.task_entry.config(font=(korean_font_name, 24))
        elif not self._is_korean(current_text) and current_font_name != default_font_name:
            self.task_entry.config(font=(default_font_name, 24))

    # ------------------- 경험치 바 업데이트 -------------------
    
    def _show_xp_bar(self):
        """XP 바와 정보를 표시합니다."""
        self.xp_canvas.place(relx=0.5, rely=0.08, anchor="n", relwidth=0.9, height=20)
        self.xp_info_label.place(relx=0.5, rely=0.11, anchor="n", relwidth=0.9)
        #self.xp_frame_spacer.pack(pady=20) # 레이아웃을 위해 스페이서 재배치
        
    def _draw_xp_bar(self):
        """XP 바를 다시 그리고 캔버스에 레벨 텍스트를 표시합니다."""
        
        # ... (캔버스 크기 및 바 그리는 로직)
        canvas_width = self.xp_canvas.winfo_width()
        canvas_height = self.xp_canvas.winfo_height()
        
        # 💡 [수정] 텍스트가 XP 바와 겹치지 않도록, 텍스트를 XP_info_label로 옮겼으므로,
        # XP 캔버스 내부에는 게이지 바만 그립니다.
        
        # (만약 XP 캔버스 안에 텍스트를 그려야 한다면:)
        # self.xp_canvas.create_text(
        #     canvas_width / 2, # X 중앙
        #     canvas_height / 2, # Y 중앙
        #     text=f"Lv.{self.current_level}", 
        #     fill="black", 
        #     font=("DungGeunMo", 12)
        # )
        
    def _hide_xp_bar(self):
        """XP 바와 정보를 숨깁니다."""
        self.xp_canvas.place_forget()
        self.xp_info_label.place_forget()
        #self.xp_frame_spacer.pack_forget()

    def update_xp_bar(self):
        """경험치 바를 현재 경험치에 맞게 업데이트합니다."""
        canvas_width = self.xp_canvas.winfo_width()
        if canvas_width < 10: 
            self.root.after(100, self.update_xp_bar)
            return
            
        progress_ratio = self.current_xp / self.total_xp_needed
        xp_width = canvas_width * progress_ratio
        
        self.xp_canvas.delete("all")
        self.xp_canvas.create_rectangle(0, 0, canvas_width, 20, fill="#ecf0f1", outline="")
        self.xp_canvas.create_rectangle(0, 0, xp_width, 20, fill="#2ecc71", outline="") # Green
        
        info_text = f"Level {self.evolution_stage} | XP: {self.current_xp}/{self.total_xp_needed}"
        self.xp_info_label.config(text=info_text)
        
    def clear_task_list(self):
        """
        할 일 목록 프레임 내의 모든 TaskItem 위젯을 파괴하여 목록을 비웁니다.
        """
        # self.task_list_frame은 TaskItem 위젯들의 부모 프레임입니다.
        for widget in self.task_list_frame.winfo_children():
            widget.destroy()
            
        # 캔버스의 스크롤 영역을 초기화 (빈 상태로 업데이트)
        self.update_scrollregion() 
        
        # 💡 [필수] 내부 데이터 구조(예: self.task_items 리스트 등)도 함께 비워야 합니다.
        # self.task_items 리스트를 사용하고 있다면:
        # self.task_items.clear()

    # ------------------- 할 일 추가 로직 -------------------

    def add_task(self):
        """사용자가 입력한 할 일을 목록에 추가합니다."""
        if not self.is_logged_in:
            messagebox.showwarning("경고", "로그인이 필요합니다.")
            return

        task_name = self.task_entry.get().strip()
        is_recurring = self.is_recurring.get()
        due_date = self.due_date_str.get()
        
        if due_date == "마감일 선택":
            due_date = ""

        if task_name:
            if due_date:
                try:
                    due_date_obj = datetime.datetime.strptime(due_date, '%Y-%m-%d').date()
                    if due_date_obj < datetime.date.today():
                        messagebox.showerror("오류", "마감일이 이미 지난 태스크는 추가할 수 없습니다.")
                        self.due_date_str.set("마감일 선택") # 입력 초기화
                        return
                except ValueError:
                    pass 

            task_item = TaskItem(
                self.task_list_frame, 
                task_name, 
                self, 
                is_recurring=is_recurring,
                due_date=due_date
            )
            task_item.pack(fill="x", padx=10, pady=2)
            
            self.task_entry.delete(0, tk.END)
            self.is_recurring.set(False)
            self.due_date_str.set("마감일 선택")
            
            print(f"새 태스크 추가: {task_name}")
            self.save_user_data()
            
            self.task_list_canvas.update_idletasks()
            self.task_list_canvas.yview_moveto(1)
        else:
            print("경고: 태스크 이름이 비어 있습니다.")
            
    def _check_pokemon_load_completion(self, future):
        """백그라운드 포켓몬 로드 작업이 완료되었는지 확인하고 UI를 업데이트합니다."""
        if future.done():
            try:
                raw_image = future.result()
                
                # 💡 [핵심] 로딩 완료 후 애니메이션 중지
                self._stop_loading_animation() 
                
                if raw_image:
                    # 이미지 표시 (비율 유지 로직이 포함된 함수)
                    self._update_pokemon_display(raw_image)
                    self.current_pil_image = raw_image # 원본 이미지 저장
                    
                    # 💡 [추가] 포켓몬 로드 완료 시 로그아웃 버튼 표시
                    self.logout_button.place(relx=1.0, rely=0.0, x=-10, y=10, anchor="ne")
                    # (혹은 place 대신 pack을 사용했다면: self.logout_button.pack(side="right", padx=(0, 10)))

                else:
                    self.image_label.config(text="이미지 로드 실패", font=self.korean_font)

            except Exception as e:
                print(f"포켓몬 데이터 로드 중 오류 발생: {e}")
                self.image_label.config(text="이미지 로드 실패", font=self.korean_font)
                self._stop_loading_animation() # 실패해도 멈춰야 함

        else:
            # 아직 로딩 중이면 100ms 후 다시 확인
            self.root.after(100, self._check_pokemon_load_completion, future)

    # ------------------- GUI 위젯 및 배치 -------------------

    def create_widgets(self):
        """메인 프레임에 위젯을 생성하고 초기 위치에 배치합니다."""
        
        title_font = tkfont.Font(
            family=self.default_font[0],
            size=30,
            weight="bold",
            slant="roman"
        )

        # 1. 제목 라벨
        self.title_label = tk.Label(
            self.main_frame, 
            text="To Do Monster", 
            font=title_font, 
            bg="Ivory", 
            fg="#F39C12"
        )
        self.title_label.place(relx=0.5, rely=0.03, anchor="n") # 상단 중앙 (3% 위치)

        # 2. 포켓몬 영역
        self.pokemon_frame = tk.Frame(self.main_frame, bg="Ivory")
        self.pokemon_frame.place(relx=0.5, rely=0.15, anchor="n", relwidth=0.9, height=200)
        
        self.image_label = tk.Label(
            self.pokemon_frame,
            bg="Ivory",
            text="로딩 중...", # 초기 텍스트
            font=("DungGeunMo", 14)
        )
        # 이미지 레이블 크기 고정 및 팩
        self.image_label.config(width=self.POKEMON_IMAGE_SIZE[0], height=self.POKEMON_IMAGE_SIZE[1])
        self.image_label.pack_propagate(False) 
        self.image_label.pack(pady=(10, 0))
        
        """self.pokemon_info_label = tk.Label(
            self.pokemon_frame,
            text="이름: ?, 도감번호: ?",
            bg="Ivory",
            font=self.korean_font
        )
        self.pokemon_info_label.pack(pady=(0, 10))"""

        # 3. 💡 [수정] 경험치 바 (타이틀 가림 방지 및 place 배치)
        self.xp_frame = tk.Frame(self.main_frame, bg="LightGray")
        # 포켓몬 영역(0.15~약 0.38) 아래인 0.40 위치에 배치
        self.xp_frame.place(relx=0.5, rely=0.45, anchor="n", relwidth=0.9, height=40)
        
        #경험치 정보 레이블
        self.xp_info_label = tk.Label(
            self.xp_frame, 
            text="Lv.? 이름:? (0/100)", # 초기 텍스트
            bg="Ivory", 
            font=("pixelFont-7-8x14-sproutLands", 10)
        )
        self.xp_info_label.pack(side="top", fill="x", pady=(0,0)) # XP 프레임 내부에 배치
        
        #경험치 캔버스
        self.xp_canvas = tk.Canvas(self.xp_frame, bg="Ivory", highlightthickness=0)
        self.xp_canvas.pack(side="bottom", fill="x", expand=True, pady=(0,0)) # XP 프레임 내부에 배치

        # 4. 💡 [수정] 로그아웃 버튼 (XP 바 밑으로, place 배치)
        self.button_frame = tk.Frame(self.main_frame, bg="Ivory")
        self.button_frame.place(relx=0.5, rely=0.52, anchor="n", relwidth=0.9, height=30) # XP 바 아래로 이동 (0.45 + 40px/H)
        
        self.logout_button = tk.Button(
            self.button_frame,
            text="로그아웃",
            font=("DungGeunMo", 10),
            command=self._logout_user,
            bg="#e74c3c",  # Red
            fg="white"
        )
        self.logout_button.pack(side="right", padx=10, pady=2) # button_frame 내에서 pack 사용

        # 5. 💡 [수정] 할 일 입력 프레임 (rely=0.55로 이동)
        self.input_frame = tk.Frame(self.main_frame, bg="Ivory")
        self.input_frame.place(relx=0.5, rely=0.58, anchor="n", relwidth=0.9)

        self.task_entry = tk.Entry(self.input_frame, font=(self.default_font[0], 24))
        self.task_entry.pack(side="left", fill="x", expand=True, padx=(0, 5))
        self.task_entry.bind('<Return>', lambda e: self.add_task())

        self.add_button = tk.Button(
            self.input_frame,
            text="추가",
            command=self.add_task,
            bg="#2ECC71", 
            fg="white",
            font=self.korean_font
        )
        self.add_button.pack(side="right", fill="y", padx=(5, 0))

        # 6. 💡 [수정] 태스크 옵션 프레임 (rely=0.62로 이동)
        self.task_options_frame = tk.Frame(self.main_frame, bg="Ivory")
        self.task_options_frame.place(relx=0.5, rely=0.65, anchor="n", relwidth=0.9)

        # ... (self.recurring_checkbox 및 self.due_date_button 코드는 그대로 유지)
        self.recurring_checkbox = tk.Checkbutton(self.task_options_frame, text="매일 반복", variable=self.is_recurring, bg="Ivory", activebackground="Ivory", font=self.korean_font)
        self.recurring_checkbox.pack(side="left")

        self.due_date_button = tk.Button(self.task_options_frame, textvariable=self.due_date_str, command=self._show_calendar_popup, bg="#e67e22", fg="white", font=self.korean_font)
        self.due_date_button.pack(side="left", padx=5)

        # 7. 💡 [수정] 할 일 목록 영역 (rely=0.68로 이동)
        self.task_canvas_frame = tk.Frame(self.main_frame, bg="Ivory")
        self.task_canvas_frame.place(relx=0.5, rely=0.71, anchor="n", relwidth=0.9, relheight=0.25)
    
        # ... (이하 task_list_canvas, scrollbar, task_list_frame 관련 코드는 그대로 유지)
        self.task_list_canvas = tk.Canvas(self.task_canvas_frame, bg="Ivory", highlightthickness=0)
        self.task_list_canvas.pack(side="left", fill="both", expand=True)

        self.task_list_scrollbar = tk.Scrollbar(self.task_canvas_frame, orient="vertical", command=self.task_list_canvas.yview)
        self.task_list_scrollbar.pack(side="right", fill="y")

        self.task_list_canvas.config(yscrollcommand=self.task_list_scrollbar.set)
        
        self.task_list_frame = tk.Frame(self.task_list_canvas, bg="Ivory")
        self.task_list_canvas.create_window((0, 0), window=self.task_list_frame, anchor="nw", tags="self.task_list_frame")
        
        self.task_list_frame.bind("<Configure>", lambda e: self.update_scrollregion())
        self.task_list_canvas.bind_all('<MouseWheel>', self._on_mousewheel) 
        self.task_list_canvas.bind_all('<Button-4>', self._on_mousewheel) 
        self.task_list_canvas.bind_all('<Button-5>', self._on_mousewheel) 
        
        self.task_list_canvas.bind("<ButtonPress-1>", self._start_drag)
        self.task_list_canvas.bind("<B1-Motion>", self._on_drag)
        
    def _show_calendar_popup(self):
        """달력 팝업을 표시하여 마감일을 선택하게 합니다."""
        top = tk.Toplevel(self.root)
        top.title("마감일 선택")
        top.attributes('-topmost', 'true')
        
        now = datetime.date.today()
        cal = Calendar(
            top, 
            selectmode='day', 
            year=now.year, 
            month=now.month, 
            day=now.day,
            date_pattern='yyyy-mm-dd',
            background="#2c3e50",
            normalbackground="white",
            foreground="black",
            selectforeground="#ecf0f1",
            selectbackground="#e74c3c",
            headersbackground="#34495e",
            headersforeground="white"
        )
        cal.pack(padx=10, pady=10)
        
        def set_due_date():
            selected_date = cal.get_date()
            self.due_date_str.set(selected_date)
            top.destroy()
            
        confirm_button = tk.Button(
            top, 
            text="확인", 
            command=set_due_date,
            bg="#2ecc71",
            fg="white"
        )
        confirm_button.pack(pady=5)
        
        close_button = tk.Button(
            top, 
            text="취소", 
            command=top.destroy,
            bg="#e74c3c",
            fg="white"
        )
        close_button.pack(pady=(0, 10))

    # ------------------- 스크롤 이벤트 핸들러 -------------------

    def _on_mousewheel(self, event):
        """마우스 휠 스크롤을 처리합니다."""
        if sys.platform.startswith('win'):
            delta = event.delta // 120
        elif sys.platform.startswith('linux'):
            delta = -1 if event.num == 5 else 1
        elif sys.platform == 'darwin':
            delta = 1 if event.delta > 0 else -1
        else:
            return

        self.task_list_canvas.yview_scroll(-delta, "units")

    def _start_drag(self, event):
        """스크롤 드래그 시작 시 Y 좌표를 저장합니다."""
        self.task_list_canvas.configure(cursor="hand2")
        self.last_y = event.y

    def _on_drag(self, event):
        """스크롤 드래그 중 캔버스를 이동시킵니다."""
        delta_y = self.last_y - event.y
        self.task_list_canvas.yview_scroll(delta_y, "units")
        self.last_y = event.y
        
if __name__ == "__main__":
    # PILLOW 라이브러리가 Tkinter의 이미지를 처리할 수 있도록 Image.ANTIALIAS 대체
    if not hasattr(Image, 'Resampling'):
        Image.Resampling = Image
    if not hasattr(Image.Resampling, 'LANCZOS'):
        Image.Resampling.LANCZOS = Image.ANTIALIAS
    
    root = tk.Tk()
    app = ResponsiveApp(root, aspect_ratio=(9, 16)) # 모바일 세로 비율 (9:16)
    root.mainloop()