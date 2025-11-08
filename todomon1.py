import tkinter as tk
import requests
from PIL import Image, ImageTk
from io import BytesIO
import random
import threading
import concurrent.futures
from tkinter import font as tkfont
import sys # Linux 휠 이벤트 처리를 위해 sys 모듈 추가

# -----------------------------------------------------------
# 할 일 항목 클래스 (TaskItem)
# -----------------------------------------------------------
class TaskItem(tk.Frame):
    """체크박스와 레이블을 포함하는 단일 할 일 항목을 나타냅니다."""
    def __init__(self, parent_frame, task_name, app_instance):
        super().__init__(parent_frame, bg="Ivory")
        self.task_name = task_name
        self.app = app_instance
        # 💡 체크박스 상태: 기본값 False (체크되지 않음)
        self.is_completed = tk.BooleanVar(value=False) 
        
        # 💡 체크박스 위젯
        self.checkbox = tk.Checkbutton(
            self, 
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
            self, 
            text=task_name, 
            bg="Ivory",
            font=current_font,
            anchor="w"
        )
        self.label.pack(side="left", fill="x", expand=True)
        
    def toggle_complete(self):
        """체크박스 상태를 토글하고 콘솔에 출력합니다. (XP 획득 로직 연결 필요)"""
        state = self.is_completed.get()
        print(f"태스크 '{self.task_name}' 완료 상태: {state}로 변경됨")
        
        # 체크되었을 때 경험치 획득 로직을 호출 (예: 10 XP)
        if state:
            self.app.gain_xp(10) 
            # 완료된 항목 스타일 변경 (취소선, 회색 등) 로직은 필요시 추가
        
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
    
class ResponsiveApp:
    """
    Tkinter 기반의 반응형 (9:16 비율) 애플리케이션 클래스입니다.
    PokeAPI에서 미진화체 포켓몬 리스트를 비동기로 로드하고,
    랜덤 포켓몬 이미지를 불러와 좌측 상단에 표시하며, 경험치 바를 표시합니다.
    """
    
    def __init__(self, root, aspect_ratio=(9, 16)):
        # 1. 초기 설정 및 변수 초기화
        self.root = root
        self.root.title("ToDoMonster")
        self.root.geometry("540x960") # 초기 크기 설정 (9:16 비율)
        self.ratio = aspect_ratio
        
        self.base_pokemon_ids = []
        
        self.current_pokemon_id = 0
        self.evolution_chain_ids = []
        
        self.completed_chains = {}
        
        # XP 변수
        self.current_xp = 0
        self.total_xp_needed = EvolutionXP.get_xp_needed(1)
        self.evolution_stage = 1
        
        # UI/GIF 변수
        self.loading_animation_id = None
        self.gif_frames = []
        self.frame_index = 0
        self.current_gif_display_width = 0
        self.current_gif_display_height = 0
        
        #폰트 설정
        self.default_font = ("pixelFont-7-8x14-sproutLands", 14)
        self.korean_font = ("pixelroborobo", 14)
        
        # 💡 드래그 스크롤 변수 추가
        self.last_y = 0
        
        # 2. 메인 프레임 설정
        self.main_frame = tk.Frame(root, bg="Ivory")
        root.grid_rowconfigure(0, weight=1)
        root.grid_columnconfigure(0, weight=1)
        self.main_frame.grid(row=0, column=0, sticky="nsew")
        
        # 3. 위젯 생성 및 로딩 시작
        self.root.bind('<Configure>', self.resize) 
        self.create_widgets()
        
        # 한글 입력 감지
        self.task_entry.bind('<KeyRelease>', self._check_korean_input)
        
        print("미진화체 리스트 로딩 중...")
        self.update_xp_bar() # 경험치 바 초기 업데이트
        
        self._load_gif_frames()
        self._animate_loading()
        threading.Thread(target=self.load_base_list_async, daemon=True).start()
        
    # ------------------- GIF 로딩 및 애니메이션 -------------------
    
    def _load_gif_frames(self):
        """GIF 파일의 모든 프레임을 로드하고 크기를 조정하여 리스트에 저장합니다."""
        try:
            gif = Image.open("loading.gif")
            max_gif_width, max_gif_height = 180, 100
            original_width, original_height = gif.size
            
            if original_width > max_gif_width or original_height > max_gif_height:
                scale = min(max_gif_width / original_width, max_gif_height / original_height)
                new_width = int(original_width * scale)
                new_height = int(original_height * scale)
            else:
                new_width = original_width
                new_height = original_height
                
            self.current_gif_display_width = new_width
            self.current_gif_display_height = new_height
            
            while True:
                # LANCZOS는 이미지 리사이징에 적합한 고품질 필터
                frame = ImageTk.PhotoImage(gif.copy().resize(
                    (new_width, new_height), Image.Resampling.LANCZOS))
                self.gif_frames.append(frame)
                gif.seek(gif.tell() + 1)
                
        except EOFError:
            pass
        
        except FileNotFoundError:
            print("경고: 'loading.gif' 파일을 찾을 수 없습니다. 애니메이션이 표시되지 않습니다.")
            
        except Exception as e:
            error_message = str(e)
            if "no more images in GIF file" not in error_message:
                print(f"GIF 로딩 중 예상치 못한 오류 발생: {e}")

    def _animate_loading(self):
        """저장된 GIF 프레임을 순차적으로 오른쪽 하단에 표시합니다."""
        if not self.gif_frames: return

        self.image_label.config(width=self.current_gif_display_width, height=self.current_gif_display_height)
        self.image_label.place(relx=1.0, rely=1.0, anchor="se", x=-10, y=-10)

        self.image_label.config(image=self.gif_frames[self.frame_index])
        self.frame_index = (self.frame_index + 1) % len(self.gif_frames)
        
        self.loading_animation_id = self.root.after(100, self._animate_loading)
        
    def _stop_loading_animation(self):
        """로딩 애니메이션을 중지하고 Label을 초기화하여 좌측 상단으로 이동시킵니다."""
        if self.loading_animation_id:
            self.root.after_cancel(self.loading_animation_id)
            self.loading_animation_id = None

        self.image_label.config(image='', width=200, height=200, text="")
        self.image_label.place(relx=0.0, rely=0.0, anchor="nw", x=10, y=10)
        self.image_label.image = None
        
    # ------------------- 포켓몬 데이터 로딩 (비동기) -------------------

    def load_base_list_async(self):
        "미진화체 리스트를 백그라운드에서 로딩하고 결과를 메인 스레드에 전달합니다."
        base_ids = self.get_base_form_pokemon_ids()
        
        if base_ids:
            self.base_pokemon_ids = base_ids
            self.root.after(0, lambda: [
                self._stop_loading_animation(),
                print(f"미진화체 리스트 로딩 완료: {len(self.base_pokemon_ids)}마리"),
                self._show_xp_bar(),
                self.start_search_thread() # 리스트 로드 완료 후 검색 시작
            ])
        else:
            self.root.after(0, lambda: [
                self._stop_loading_animation(),
                print("미진화체 리스트 로딩 실패")
            ])
            self.base_pokemon_ids = list(range(1, 11)) # 실패 시 기본값 설정
            
    def get_base_form_pokemon_ids(self):
        """PokeAPI에서 미진화체 포켓몬 ID 리스트를 가져옵니다 (병렬 처리 사용)."""
        chain_list_url = "https://pokeapi.co/api/v2/evolution-chain/?limit=1000"
        
        try:
            response = requests.get(chain_list_url, timeout=10)
            response.raise_for_status() 
            all_chain_urls = [res['url'] for res in response.json().get('results', [])]
            base_ids = []
            
            def fetch_base_id_from_chain(chain_detail_url):
                try:
                    detail_response = requests.get(chain_detail_url, timeout=5)
                    if detail_response.status_code != 200:
                        return None
                        
                    chain_data = detail_response.json()
                    chain_structure = chain_data.get('chain', {})
                    base_species_url = chain_structure.get('species', {}).get('url')
                    
                    # 진화체가 없는 단일 포켓몬은 제외
                    if not chain_structure.get('evolves_to'):
                        return None
                    
                    if not base_species_url:
                        return None

                    pokemon_id = base_species_url.strip('/').split('/')[-1]
                    
                    species_url = f"https://pokeapi.co/api/v2/pokemon-species/{pokemon_id}"
                    species_response = requests.get(species_url, timeout=5)
                    if species_response.status_code != 200: return None
                        
                    species_data = species_response.json()
                    
                    # 전설/환상 필터링
                    if (not species_data.get('is_legendary') and not species_data.get('is_mythical')):
                        return int(pokemon_id)
                    return None
                        
                except requests.exceptions.RequestException:
                    return None
                        
            with concurrent.futures.ThreadPoolExecutor(max_workers=8) as executor:
                futures = [executor.submit(fetch_base_id_from_chain, url) for url in all_chain_urls]
                for future in concurrent.futures.as_completed(futures):
                    pokemon_id = future.result()
                    if pokemon_id is not None:
                        base_ids.append(pokemon_id)
                        
            return base_ids
            
        except requests.exceptions.RequestException:
            return None
        
    def _hide_xp_bar(self):
        """경험치 바를 숨깁니다."""
        self.xp_canvas.place_forget()
        self.task_entry.place_forget()
        self.add_task_button.place_forget()
            
    def _show_xp_bar(self):
        """경험치 바를 다시 표시합니다."""
        self.xp_canvas.place(
            relx=1.0, 
            rely=0.05, 
            anchor="ne", 
            x=-10, 
            y=self.title_label.winfo_reqheight() + 10, 
            relwidth=0.6)
        
        # 위젯 배치를 다시 계산하여 표시
        self.task_entry.place(
            relx=0.95, 
            rely=0.95, 
            anchor="e", 
            relwidth=0.73, 
            x=-(10 + self.main_frame.winfo_width() * 0.20 + 5)
        )
        self.add_task_button.place(
            relx=0.95, rely=0.95, anchor="e", relwidth=0.20, x=-10
        )
            
        self.update_xp_bar()
        
    def _is_korean(self, text):
        """주어진 텍스트에 한글 문자가 포함되어 있는지 확인합니다."""
        if not text:
            return False
        # 한글 유니코드 범위: 가(0xAC00) ~ 힣(0xD7A3)
        for char in text:
            if 0xAC00 <= ord(char) <= 0xD7A3:
                return True
        return False
    
    def _check_korean_input(self, event):
        """
        키 입력이 해제될 때마다 입력된 텍스트를 확인하고 폰트를 변경합니다.
        """
        current_text = self.task_entry.get()
        # 현재 폰트 이름 추출 (예: 'pixelFont-7-8x14-sproutLands 14' -> 'pixelFont-7-8x14-sproutLands')
        current_font_name = self.task_entry.cget("font").split()[0] 
        
        if self._is_korean(current_text) and current_font_name != self.korean_font[0]:
            # 한글이 포함되어 있고 현재 폰트가 한국어 폰트가 아니라면 변경
            self.task_entry.config(font=self.korean_font)
            print(f"폰트 변경: {current_font_name} -> {self.korean_font[0]}")
        elif not self._is_korean(current_text) and current_font_name != self.default_font[0]:
            # 한글이 없고 현재 폰트가 기본 폰트가 아니라면 변경
            self.task_entry.config(font=self.default_font)
            

    def _get_evolution_chain_ids(self, base_pokemon_id):
        """포켓몬 ID를 이용해 해당 종의 진화 체인 내 모든 포켓몬 ID를 순서대로 가져옵니다 (단일 경로)."""
        species_url = f"https://pokeapi.co/api/v2/pokemon-species/{base_pokemon_id}"
        try:
            response = requests.get(species_url, timeout=5)
            response.raise_for_status()
            data = response.json()
            chain_url = data.get('evolution_chain', {}).get('url')
        except requests.exceptions.RequestException:
            return []
        
        if not chain_url:
            return []
        
        try:
            response = requests.get(chain_url, timeout=5)
            response.raise_for_status()
            chain_data = response.json()
        except requests.exceptions.RequestException:
            return []
        
        # 핵심 수정 사항 1: 재귀 함수 정의와 호출을 메서드 내부에 올바르게 포함
        def get_simple_chain(chain_link):
            """단일 경로만 따라가며 ID를 추출합니다 (이브이 등 분기 진화는 첫 번째 경로만 선택)."""
            
            if not chain_link:
                return []
            
            species_url = chain_link.get('species', {}).get('url')
            if not species_url: return []
            
            species_id = species_url.strip('/').split('/')[-1]
            ids = [int(species_id)]
            
            next_links = chain_link.get('evolves_to', [])
            if next_links:
                ids.extend(get_simple_chain(next_links[0]))
                
            return ids
        
        # 중복 제거를 위해 dict.fromkeys를 사용
        return list(dict.fromkeys(get_simple_chain(chain_data.get('chain', {}))))

    def _initial_load_pokemon_chain(self, base_id):
        """베이스 포켓몬의 체인을 로드하고 첫 단계를 표시합니다"""
        chain_ids = self._get_evolution_chain_ids(base_id)
        
        if not chain_ids:
            self.root.after(0, lambda: print("오류: 진화 체인 로드 실패. 새로운 포켓몬을 시도합니다."))
            self.root.after(100, self.start_search_thread)
            return
        
        self.evolution_chain_ids = chain_ids
        self.evolution_stage = 1
        self.current_pokemon_id = chain_ids[0]
        
        self.display_pokemon(self.current_pokemon_id)
        
        self.total_xp_needed = EvolutionXP.get_xp_needed(self.evolution_stage)
        self.current_xp = 0
        self.root.after(0, self.update_xp_bar)
        
    def load_pokemon_data(self, pokemon_id):
        """PokeAPI에서 포켓몬 데이터를 가져오고, 이미지를 다운로드하여 반환합니다."""
        url = f"https://pokeapi.co/api/v2/pokemon/{pokemon_id}"
        
        try:
            response = requests.get(url, timeout=10)
            response.raise_for_status() 
            data = response.json()
            # 공식 아트워크 URL 추출
            image_url = data['sprites']['other']['official-artwork']['front_default']
            
            image_response = requests.get(image_url, timeout=10)
            image_response.raise_for_status()
            
            pil_image = Image.open(BytesIO(image_response.content))
            
            width, height = pil_image.size
            max_size = 200
            if width > max_size or height > max_size:
                pil_image.thumbnail((max_size, max_size))
                width, height = pil_image.size

            tk_image = ImageTk.PhotoImage(pil_image)
            status_text = f"이름: {data['name'].capitalize()}, 도감번호: {data['id']}"
            
            return tk_image, status_text, width, height
            
        except requests.exceptions.HTTPError as errh:
            status_code = response.status_code if 'response' in locals() else 'Unknown'
            return None, f"오류: 포켓몬 ID {pokemon_id}를 찾을 수 없습니다. (HTTP: {status_code})", 0, 0
        except requests.exceptions.RequestException as e:
            return None, "오류: 네트워크 연결 또는 다운로드 오류가 발생했습니다." , 0, 0
            
    # ------------------- 포켓몬 이미지 검색 및 표시 -------------------

    def start_search_thread(self, event=None):
        """랜덤 포켓몬을 선택하고, 별도의 스레드에서 검색 작업을 시작합니다."""
        
        if not self.base_pokemon_ids:
            print("리스트 로드 중...")
            self._hide_xp_bar()
            self._animate_loading()
            return
        
        random_base_id = random.choice(self.base_pokemon_ids)
        print(f"랜덤 포켓몬 ID 생성: {random_base_id}")

        self.root.after(0, self._stop_loading_animation)
        self.image_label.config(image='')
        
        thread = threading.Thread(target=self._initial_load_pokemon_chain, args=(random_base_id,), daemon=True)
        thread.start()
        
    def display_pokemon(self, pokemon_id):
        """백그라운드에서 포켓몬 데이터를 로드하고, 메인 스레드에 업데이트를 요청합니다."""

        tk_image, status_text, width, height = self.load_pokemon_data(pokemon_id)
        self.root.after(0, lambda: self.update_gui(tk_image, status_text, width, height))

    def update_gui(self, tk_image, status_text, img_width, img_height):
        """API 호출 결과를 사용하여 GUI 위젯을 업데이트합니다 (메인 스레드에서 실행)."""
        print(status_text)
        
        if tk_image:
            self.image_label.config(image=tk_image, width=img_width, height=img_height)
            self.image_label.image = tk_image
        else:
            self.image_label.config(image='', width=150, height=150, text="이미지 로드 실패")
            self.image_label.image = None
            
    # ------------------- XP 증가 및 진화 로직 -------------------
    
    def gain_xp(self, amount):
        """경험치를 증가시키고 진화/재선택 로직을 처리합니다."""
        
        self.current_xp += amount
        self.root.after(0, self.update_xp_bar)
        
        if self.current_xp >= self.total_xp_needed:
            next_stage_index = self.evolution_stage
            
            if next_stage_index < len(self.evolution_chain_ids):
                # 진화
                self.evolution_stage += 1
                self.current_pokemon_id = self.evolution_chain_ids[next_stage_index]
                self.current_xp = 0
                # 다음 단계 필요 XP 계산
                self.total_xp_needed = EvolutionXP.get_xp_needed(self.evolution_stage) 
                
                print(f"🎉 진화! 다음 단계 XP: {self.total_xp_needed}, ID: {self.current_pokemon_id}")
                
                self.root.after(0, self._stop_loading_animation)
                thread = threading.Thread(target=self.display_pokemon, args=(self.current_pokemon_id,), daemon=True)
                thread.start()
                
            else:
                # 진화 체인 끝: 새로운 포켓몬 선택
                print("✨ 진화 체인 끝! 새로운 포켓몬을 선택합니다.")
                
                base_id = self.evolution_chain_ids[0]
                self.completed_chains[base_id] = self.evolution_chain_ids
                print(f"✅ 진화 체인 저장 완료 (Base ID {base_id}): {self.completed_chains[base_id]}")
                
                # 상태 초기화
                self.current_xp = 0
                self.evolution_stage = 1
                self.current_pokemon_id = 0
                self.evolution_chain_ids = []
                self.total_xp_needed = EvolutionXP.get_xp_needed(1)
                
                self.start_search_thread() # 새로운 포켓몬 로드
                
    # ------------------- 새롭게 추가된 태스크 처리 로직 -------------------
    def _add_task(self):
        """입력된 태스크를 처리하고 TaskItem 위젯을 추가합니다."""
        task_name = self.task_entry.get().strip()
        
        if task_name:
            new_task = TaskItem(
                parent_frame=self.task_list_frame, 
                task_name=task_name, 
                app_instance=self
            )
            new_task.pack(fill="x", pady=2, padx=5)
            
            print(f"새 태스크 추가: {task_name}")
            
            self.task_entry.delete(0, tk.END)
            
            # 스크롤 영역이 업데이트된 후, 가장 아래로 스크롤
            self.task_list_canvas.update_idletasks() 
            self.task_list_canvas.yview_moveto(1)
        else:
            print("경고: 태스크 이름이 비어 있습니다.")

    # ------------------- 경험치 바 업데이트 -------------------
    def update_xp_bar(self):
        """경험치 바를 현재 경험치에 맞게 업데이트합니다."""
        canvas_width = self.xp_canvas.winfo_width()
        if canvas_width < 10: # 초기 로딩 시 폭이 1로 잡히는 경우가 있어 최소값 설정
            canvas_width = 300
            
        self.xp_canvas.delete("bar")
        self.xp_canvas.delete("xp_text")
        
        if self.total_xp_needed > 0:
            progress_ratio = min(self.current_xp / self.total_xp_needed, 1.0)
        else:
            progress_ratio = 0.0
            
        fill_width = canvas_width * progress_ratio
        
        self.xp_canvas.create_rectangle(
            1, 1, fill_width, self.xp_canvas_height,
            fill="#7CFC00", # 잔디색 (Bright Green)
            outline="",
            tags="bar"
        )
        
        # 캔버스 테두리
        self.xp_canvas.create_rectangle(
            1, 1, canvas_width, self.xp_canvas_height,
            outline="black",
            width=2
        )
        
        # 캔버스 내부에 텍스트 추가
        xp_text = f"XP: {self.current_xp}/{self.total_xp_needed} (Lvl {self.evolution_stage})"
        
        self.xp_canvas.create_text(
            canvas_width / 2, 
            self.xp_canvas_height / 2,
            text=xp_text,
            fill="black",
            font=("custom_font", 10, "bold"),
            tags="xp_text"
        )

    # ------------------- 이벤트 핸들러 (창 크기 조정 및 스크롤) -------------------
    
    def resize(self, event):
        """창 크기가 변경될 때, 9:16 비율을 강제하여 메인 프레임 크기를 조정합니다."""
        
        window_width = self.root.winfo_width()
        window_height = self.root.winfo_height()

        ratio_w, ratio_h = self.ratio

        max_width = int(window_height * ratio_w / ratio_h)
        max_height = int(window_width * ratio_h / ratio_w)
        
        if max_width <= window_width:
            frame_w = max_width
            frame_h = window_height
            x_pos = (window_width - frame_w) // 2
            y_pos = 0
        else:
            frame_w = window_width
            frame_h = max_height
            x_pos = 0
            y_pos = (window_height - frame_h) // 2
            
        self.main_frame.place(x=x_pos, y=y_pos, width=frame_w, height=frame_h)

        self.xp_canvas.after(50, self.update_xp_bar)
        
    def _on_mousewheel(self, event):
        """마우스 휠 이벤트를 처리하여 캔버스를 스크롤합니다."""
        if sys.platform.startswith('win') or sys.platform.startswith('darwin'):
            # Windows/macOS (event.delta는 120 또는 -120)
            self.task_list_canvas.yview_scroll(int(-1*(event.delta/120)), "units")
        elif sys.platform.startswith('linux'):
            # Linux (event.num: 4=Up, 5=Down)
            if event.num == 4: 
                self.task_list_canvas.yview_scroll(-1, "units")
            elif event.num == 5:
                self.task_list_canvas.yview_scroll(1, "units")

    def _on_frame_configure(self, event):
        """Canvas의 스크롤 영역을 내부 프레임 크기에 맞게 업데이트합니다."""
        self.task_list_canvas.config(scrollregion=self.task_list_canvas.bbox("all"))

    def _start_drag_scroll(self, event):
        """드래그 스크롤 시작 시 초기 Y 좌표를 저장합니다."""
        self.last_y = event.y

    def _do_drag_scroll(self, event):
        """드래그 시 스크롤을 수행합니다."""
        # 움직인 거리의 음수만큼 스크롤 (화면을 아래로 드래그하면 콘텐츠가 위로 올라가야 함)
        self.task_list_canvas.yview_scroll(int((self.last_y - event.y) / 10), "units")
        self.last_y = event.y

    # ------------------- GUI 위젯 및 배치 -------------------

    def create_widgets(self):
        """메인 프레임에 위젯을 생성하고 초기 위치에 배치합니다."""
        
        title_font = tkfont.Font(
            family=self.default_font[0], size=30, weight="bold", slant="roman")
        
        # 1. 제목 라벨
        self.title_label = tk.Label(
            self.main_frame, 
            text="To Do Monster", 
            font=title_font, 
            bg="Ivory", 
            fg="#F14C38", # 연한 빨간색
            highlightthickness=0)
        
        self.title_label.place(relx=0.95, rely=0.05, anchor="ne", x=-10, y=0)
        
        # 2. 경험치 바 (캔버스)
        self.xp_canvas_height = 20
        self.xp_canvas = tk.Canvas(
            self.main_frame, 
            bg="White", # 경험치 바 배경을 흰색으로 변경
            height=self.xp_canvas_height, 
            highlightthickness=0 # 캔버스 자체의 하이라이트 제거
        )
        
        self.xp_canvas.place(
            relx=1.0, 
            rely=0.05, 
            anchor="ne", 
            x=-10, 
            y=self.title_label.winfo_reqheight() + 10, 
            relwidth=0.6)
        
        self.xp_canvas.place_forget()
        
        # 3. 포켓몬 이미지/로딩 표시 라벨
        self.image_label = tk.Label(self.main_frame, bg="Ivory", width=125, height=125)
        self.image_label.place(relx=0.0, rely=0.0, anchor="nw", x=10, y=10)
        
        # 4. 하단 입력 박스
        self.task_entry = tk.Entry(
            self.main_frame,
            font=self.default_font,
            bd=1,
            relief="solid"
        )
        
        # 초기 배치 (place_forget 전에 계산된 위치를 기억)
        self.task_entry.place(
            relx=0.95, 
            rely=0.95, 
            anchor="e", 
            relwidth=0.73, 
            x=-(10 + self.main_frame.winfo_width() * 0.20 + 5)
        )
        self.task_entry.place_forget()
        
        # 5. Add Task 버튼
        self.add_task_button = tk.Button(
            self.main_frame,
            text="Add Task",
            font=("custom_font", 12, "bold"),
            bg="#F14C38", # 연한 빨간색
            fg="black",
            command=self._add_task
        )
        
        self.add_task_button.place(
            relx=0.95, rely=0.95, anchor="e", relwidth=0.20, x=-10
        )
        self.add_task_button.place_forget()
        
        # 6. 태스크 리스트 영역 (Canvas 및 Inner Frame)
        self.task_list_canvas = tk.Canvas(self.main_frame, bg="Ivory", highlightthickness=0)
        self.task_list_canvas.place(
            relx=0.05, 
            rely=0.25, 
            relwidth=0.9, 
            relheight=0.65, 
            anchor="nw"
        )
        
        # 스크롤 가능한 항목들을 담을 Inner Frame 생성
        self.task_list_frame = tk.Frame(self.task_list_canvas, bg="Ivory")
        self.task_list_canvas.create_window(
            (0, 0), 
            window=self.task_list_frame, 
            anchor="nw", 
            tags="self.task_list_frame"
        )
        
        # Inner Frame 크기 변경 시 Canvas 스크롤 영역 업데이트
        self.task_list_frame.bind("<Configure>", self._on_frame_configure)
        
        # 드래그 스크롤 이벤트 바인딩
        self.task_list_canvas.bind('<ButtonPress-1>', self._start_drag_scroll) 
        self.task_list_canvas.bind('<B1-Motion>', self._do_drag_scroll) 
        
        # 마우스 휠 스크롤 바인딩
        self.root.bind_all('<MouseWheel>', self._on_mousewheel)
        self.root.bind_all('<Button-4>', self._on_mousewheel) # Linux Scroll Up
        self.root.bind_all('<Button-5>', self._on_mousewheel) # Linux Scroll Down


if __name__ == "__main__":
    # PILLOW 라이브러리가 Tkinter의 이미지를 처리할 수 있도록 Image.ANTIALIAS 대신 LANCZOS 사용
    try:
        Image.ANTIALIAS = Image.Resampling.LANCZOS
    except AttributeError:
        # 이미 최신 버전 PIL에서 제거된 속성이므로 오류 무시
        pass 
        
    root = tk.Tk()
    app = ResponsiveApp(root, aspect_ratio=(9, 16)) # 모바일 세로 비율 (9:16)
    
    root.mainloop()