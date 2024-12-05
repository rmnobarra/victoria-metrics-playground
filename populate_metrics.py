import time
import random
import requests

API_URL = "http://localhost:5000"  # URL da API de exemplo
ENDPOINTS = ["/", "/metrics"]      # Endpoints a serem chamados

def simulate_requests():
    while True:
        # Escolhe um endpoint aleatório para simular uma requisição
        endpoint = random.choice(ENDPOINTS)
        url = f"{API_URL}{endpoint}"
        
        try:
            # Faz a requisição ao endpoint
            response = requests.get(url)
            
            # Simula sucesso ou falha aleatória para algumas requisições
            if response.status_code == 200:
                print(f"[INFO] Successfully hit {url}")
            else:
                print(f"[ERROR] Received status code {response.status_code} for {url}")
        except requests.RequestException as e:
            print(f"[ERROR] Failed to hit {url}: {e}")

        # Aguarda de 0.5 a 2 segundos antes da próxima requisição
        time.sleep(random.uniform(0.5, 2.0))

if __name__ == "__main__":
    simulate_requests()
