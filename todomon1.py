import tkinter as tk
import requests
from PIL import Image, ImageTk
from io import BytesIO
import random
import threading
import concurrent.futures

class ResponsiveApp:
    """
    Tkinter 기반의 반응형 (9:16 비율) 애플리케이션 클래스입니다.
    PokeAPI에서 미진화체 포켓몬 리스트를 비동기로 로드하고,
    랜덤 포켓몬 이미지를 불러와 좌측 상단에 표시합니다.
    """
    
    def __init__(self, root, aspect_ratio=(9, 16)):
        self.root = root
        self.root.title("ToDoMonster")
        self.root.geometry("1080x1920") # 초기 크기 설정 (9:16 비율)
        self.ratio = aspect_ratio
        
        self.base_pokemon_ids = []
        
        # UI 관련 변수
        self.loading_animation_id = None
        self.gif_frames = []
        self.frame_index = 0
        self.current_gif_display_width = 0
        self.current_gif_display_height = 0
        
        # 메인 컨테이너 프레임 설정
        self.main_frame = tk.Frame(root, bg="Ivory")
        root.grid_rowconfigure(0, weight=1)
        root.grid_columnconfigure(0, weight=1)
        self.main_frame.grid(row=0, column=0, sticky="nsew")
        
        # 이벤트 바인딩 및 위젯 생성
        self.root.bind('<Configure>', self.resize) 
        self.create_widgets()
        
        print("미진화체 리스트 로딩 중...")
        
        # 비동기 로딩 시작
        self._load_gif_frames()
        self._animate_loading()
        threading.Thread(target=self.load_base_list_async, daemon=True).start()
        
    # --- GIF 로딩 및 애니메이션 관련 메서드 ---
    
    def _load_gif_frames(self):
        """GIF 파일의 모든 프레임을 로드하고 크기를 조정하여 리스트에 저장합니다."""
        try:
            gif = Image.open("loading.gif")
            
            max_gif_width, max_gif_height = 100, 56
            original_width, original_height = gif.size
            
            # GIF 크기 조정 계산
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
                frame = ImageTk.PhotoImage(gif.copy().resize(
                    (new_width, new_height), Image.Resampling.LANCZOS))
                self.gif_frames.append(frame)
                gif.seek(gif.tell() + 1)
        except EOFError:
            pass
        except FileNotFoundError:
            print("경고: 'loading.gif' 파일을 찾을 수 없습니다. 애니메이션이 표시되지 않습니다.")
        except Exception as e:
            print(f"GIF 로딩 중 오류 발생: {e}")

    def _animate_loading(self):
        """저장된 GIF 프레임을 순차적으로 오른쪽 하단에 표시합니다."""
        if not self.gif_frames:
            return

        self.image_label.config(
            width=self.current_gif_display_width,
            height=self.current_gif_display_height
        )
        
        # 로딩 위치: 오른쪽 하단 (anchor="se", South-East)
        self.image_label.place(relx=1.0, rely=1.0, anchor="se", x=-10, y=-10)

        self.image_label.config(image=self.gif_frames[self.frame_index])
        self.frame_index = (self.frame_index + 1) % len(self.gif_frames)
        
        self.loading_animation_id = self.root.after(100, self._animate_loading)
        
    def _stop_loading_animation(self):
        """로딩 애니메이션을 중지하고 Label을 초기화하여 좌측 상단으로 이동시킵니다."""
        if self.loading_animation_id:
            self.root.after_cancel(self.loading_animation_id)
            self.loading_animation_id = None
            
        self.image_label.config(image='', width=125, height=125, text="")
        # 포켓몬 이미지의 최종 위치: 좌측 상단 (anchor="nw", North-West)
        self.image_label.place(relx=0.0, rely=0.0, anchor="nw", x=10, y=10)
        self.image_label.image = None
        
    # --- 포켓몬 데이터 로딩 관련 메서드 ---

    def load_base_list_async(self):
        "미진화체 리스트를 백그라운드에서 로딩하고 결과를 메인 스레드에 전달합니다."
        base_ids = self.get_base_form_pokemon_ids()
        
        if base_ids:
            self.base_pokemon_ids = base_ids
            self.root.after(0, lambda: [
                self._stop_loading_animation(),
                print(f"미진화체 리스트 로딩 완료: {len(self.base_pokemon_ids)}마리"),
                self.start_search_thread()
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
                    if detail_response.status_code == 200:
                        chain_data = detail_response.json()
                        base_species = chain_data.get('chain', {}).get('species', {})
                        species_url = base_species.get('url')
                        if species_url:
                            # URL에서 ID 추출 (예: '.../species/1/' -> '1')
                            pokemon_id = species_url.strip('/').split('/')[-1]
                            return int(pokemon_id)
                    return None
                except requests.exceptions.RequestException:
                    return None
                
            # 병렬로 진화 체인 정보 가져오기
            with concurrent.futures.ThreadPoolExecutor(max_workers=8) as executor:
                futures = [executor.submit(fetch_base_id_from_chain, url) for url in all_chain_urls]
                
                for future in concurrent.futures.as_completed(futures):
                    pokemon_id = future.result()
                    if pokemon_id is not None:
                        base_ids.append(pokemon_id)
                        
            return base_ids
        except requests.exceptions.RequestException:
            return None

    def load_pokemon_data(self, pokemon_id):
        """
        PokeAPI에서 포켓몬 데이터를 가져오고, 이미지를 다운로드하여 Tkinter 이미지 객체로 반환합니다.
        """
        url = f"https://pokeapi.co/api/v2/pokemon/{pokemon_id}"
        
        try:
            # 1. 포켓몬 정보 API 요청
            response = requests.get(url)
            response.raise_for_status() 
            data = response.json()
            
            image_url = data['sprites']['other']['official-artwork']['front_default']
            
            # 2. 이미지 데이터 다운로드
            image_response = requests.get(image_url)
            image_response.raise_for_status()
            
            # 3. Pillow 이미지 객체로 변환 및 크기 조절
            pil_image = Image.open(BytesIO(image_response.content))
            
            width, height = pil_image.size
            max_size = 125
            if width > max_size or height > max_size:
                pil_image.thumbnail((max_size, max_size))
                width, height = pil_image.size # 조정된 크기 저장

            # 4. Tkinter PhotoImage로 변환
            tk_image = ImageTk.PhotoImage(pil_image)
            status_text = f"이름: {data['name'].capitalize()}, 도감번호: {data['id']}"
            
            return tk_image, status_text, width, height
            
        except requests.exceptions.HTTPError as errh:
            status_code = response.status_code if 'response' in locals() else 'Unknown'
            return None, f"오류: 포켓몬 ID {pokemon_id}를 찾을 수 없습니다. (HTTP: {status_code})", 0, 0
        except requests.exceptions.RequestException as e:
            return None, "오류: 네트워크 연결 또는 다운로드 오류가 발생했습니다." , 0, 0

    # --- GUI 위젯 및 배치 관련 메서드 ---

    def create_widgets(self):
        """메인 프레임에 위젯을 생성하고 초기 위치에 배치합니다."""

        # 포켓몬 이미지/로딩 표시 라벨
        self.image_label = tk.Label(self.main_frame, bg="Ivory", width=125, height=125)
        self.image_label.place(relx=0.0, rely=0.0, anchor="nw", x=10, y=10) # 좌측 상단 (여백 10px)

    def start_search_thread(self, event=None):
        """랜덤 포켓몬을 선택하고, 별도의 스레드에서 검색 작업을 시작합니다."""
        
        if not self.base_pokemon_ids:
            print("리스트 로드 중...")
            self._animate_loading()
            return
        
        # 랜덤 포켓몬 ID 생성
        random_id = random.choice(self.base_pokemon_ids)
        print(f"랜덤 포켓몬 ID 생성: {random_id}")
        
        self.root.after(0, self._stop_loading_animation)
        self.image_label.config(image='')
        
        # 백그라운드 스레드에서 API 호출 시작
        thread = threading.Thread(target=self.display_pokemon, args=(random_id,), daemon=True)
        thread.start()
        
    def display_pokemon(self, pokemon_id):
        """백그라운드에서 포켓몬 데이터를 로드하고, 메인 스레드에 업데이트를 요청합니다."""

        tk_image, status_text, width, height = self.load_pokemon_data(pokemon_id)
        # 메인 스레드에서 GUI 업데이트 실행
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

    def resize(self, event):
        """창 크기가 변경될 때, 9:16 비율을 강제하여 메인 프레임 크기를 조정합니다."""
        
        window_width = self.root.winfo_width()
        window_height = self.root.winfo_height()

        ratio_w, ratio_h = self.ratio

        # 1. 높이를 기준으로 최대 너비 계산
        max_width = int(window_height * ratio_w / ratio_h)
        # 2. 너비를 기준으로 최대 높이 계산
        max_height = int(window_width * ratio_h / ratio_w)
        
        # 프레임 크기 및 위치 결정
        if max_width <= window_width:
            # 높이 비율이 지배적: 너비를 max_width로 제한하고 중앙 배치
            frame_w = max_width
            frame_h = window_height
            x_pos = (window_width - frame_w) // 2
            y_pos = 0
        else:
            # 너비 비율이 지배적: 높이를 max_height로 제한하고 중앙 배치
            frame_w = window_width
            frame_h = max_height
            x_pos = 0
            y_pos = (window_height - frame_h) // 2
            
        # 계산된 크기와 위치를 main_frame에 적용
        self.main_frame.place(x=x_pos, y=y_pos, width=frame_w, height=frame_h)

if __name__ == "__main__":
    root = tk.Tk()
    app = ResponsiveApp(root, aspect_ratio=(9, 16)) # 모바일 세로 비율 (9:16)
    root.mainloop()