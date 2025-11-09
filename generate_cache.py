import requests
import concurrent.futures
import json
import os
import time

def fetch_base_id_from_chain(chain_detail_url):
    """주어진 진화 체인 URL에서 미진화체 포켓몬 ID를 추출합니다."""
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

        pokemon_id_str = base_species_url.strip('/').split('/')[-1]
        
        if not pokemon_id_str.isdigit():
             return None
            
        pokemon_id = int(pokemon_id_str)
            
        # 전설/환상 포켓몬 필터링을 위해 종족 정보 요청
        species_url = f"https://pokeapi.co/api/v2/pokemon-species/{pokemon_id}"
        species_response = requests.get(species_url, timeout=5)
        if species_response.status_code != 200: return None
            
        species_data = species_response.json()
        
        # 전설(is_legendary) 또는 환상(is_mythical)이 아닌 경우만 반환
        if (not species_data.get('is_legendary') and not species_data.get('is_mythical')):
            return pokemon_id
        return None
            
    except requests.exceptions.RequestException as e:
        # print(f"경고: API 요청 실패 - {e}") # 디버깅 시 주석 해제
        return None

def generate_base_ids_cache():
    """모든 미진화체 포켓몬 ID를 수집하고 JSON 파일로 저장합니다."""
    start_time = time.time()
    print("--- 캐시 파일 생성 시작 (PokeAPI 요청) ---")
    
    # 전체 진화 체인 목록을 요청 (약 500개)
    chain_list_url = "https://pokeapi.co/api/v2/evolution-chain/?limit=1000" 
    
    try:
        response = requests.get(chain_list_url, timeout=10)
        response.raise_for_status() 
        all_chain_urls = [res['url'] for res in response.json().get('results', [])]
        base_ids = []
        
        print(f"총 {len(all_chain_urls)}개의 진화 체인 URL 로드 완료. 병렬 처리 시작...")

        # 워커 수 32를 사용하여 최대한 빠르게 병렬 요청
        with concurrent.futures.ThreadPoolExecutor(max_workers=32) as executor:
            futures = [executor.submit(fetch_base_id_from_chain, url) for url in all_chain_urls]
            
            for i, future in enumerate(concurrent.futures.as_completed(futures)):
                pokemon_id = future.result()
                if pokemon_id is not None:
                    base_ids.append(pokemon_id)
                
                # 100개마다 진행 상황 출력
                if (i + 1) % 100 == 0 or (i + 1) == len(all_chain_urls):
                    print(f"진행 상황: {i + 1}/{len(all_chain_urls)} (수집된 ID: {len(base_ids)})")
                    
        # 중복 제거 및 정렬
        final_base_ids = sorted(list(set(base_ids)))
        
        # JSON 파일로 저장
        cache_file_path = "base_ids.json"
        with open(cache_file_path, "w", encoding="utf-8") as f:
            json.dump(final_base_ids, f, indent=4)
            
        end_time = time.time()
        
        print("\n--- 캐시 파일 생성 완료 ---")
        print(f"총 미진화체 포켓몬 수: {len(final_base_ids)}마리")
        print(f"파일 저장 경로: {os.path.abspath(cache_file_path)}")
        print(f"총 소요 시간: {end_time - start_time:.2f}초")
        
    except requests.exceptions.RequestException as e:
        print(f"\n[오류] 네트워크 요청 실패: {e}")
        print("API 서버 상태를 확인하거나 네트워크 연결을 점검하세요.")
    except Exception as e:
        print(f"\n[오류] 예상치 못한 오류 발생: {e}")

if __name__ == "__main__":
    generate_base_ids_cache()