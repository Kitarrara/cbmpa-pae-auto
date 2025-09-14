import os
from dotenv import load_dotenv
from sheets import SheetUpdater
from scrape_pae import PAEClient

def main():
    load_dotenv()
    sheet_id = os.environ["SHEET_ID"]
    tab_name = os.getenv("SHEET_TAB_NAME", "Processos 2025")

    updater = SheetUpdater(sheet_id=sheet_id, tab_name=tab_name)
    pae = PAEClient()

    # Lê a coluna "PAE" (obrigatória) e um dicionário {row_index: pae_number}
    pae_map = updater.read_pae_numbers()

    for row_idx, pae_number in pae_map.items():
        print(f"[INFO] Coletando: {pae_number}")
        data = pae.fetch_process_data(pae_number)
        if not data:
            print(f"[WARN] Não foi possível coletar dados para {pae_number}. Pulando.")
            continue
        # Atualiza a linha com os campos retornados
        updater.update_row_by_headers(row_idx, data)

    print("[OK] Finalizado.")

if __name__ == "__main__":
    main()
