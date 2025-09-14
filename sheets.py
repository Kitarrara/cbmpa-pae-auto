import os
import json
import gspread
from datetime import datetime
from google.oauth2 import service_account

REQUIRED_HEADERS = [
    "PAE",
    "Objeto",
    "Rito / Modalidade",
    "Etapa atual",
    "Dias na etapa",
    "Setor atual",
    "Valor",
    "Situação",
    "Última atualização",
    "Link PAE"
]

class SheetUpdater:
    def __init__(self, sheet_id: str, tab_name: str):
        creds_json = os.environ["GOOGLE_SERVICE_ACCOUNT_JSON"]
        info = json.loads(creds_json)
        scopes = [
            "https://www.googleapis.com/auth/spreadsheets",
            "https://www.googleapis.com/auth/drive"
        ]
        creds = service_account.Credentials.from_service_account_info(info, scopes=scopes)
        gc = gspread.authorize(creds)
        sh = gc.open_by_key(sheet_id)

        self.ws = None
        # Tenta abrir por nome, senão pega a primeira
        try:
            self.ws = sh.worksheet(tab_name)
        except Exception:
            self.ws = sh.sheet1

        self.ensure_headers()

    def ensure_headers(self):
        values = self.ws.get_all_values()
        if not values:
            self.ws.append_row(REQUIRED_HEADERS)
            return

        headers = values[0]
        changed = False
        for h in REQUIRED_HEADERS:
            if h not in headers:
                headers.append(h)
                changed = True
        if changed:
            self.ws.update('1:1', [headers])

    def header_index(self, header):
        headers = self.ws.row_values(1)
        try:
            return headers.index(header) + 1  # 1-based
        except ValueError:
            # cria ao final
            headers.append(header)
            self.ws.update('1:1', [headers])
            return len(headers)

    def read_pae_numbers(self):
        values = self.ws.get_all_values()
        if not values:
            return {}

        headers = values[0]
        if "PAE" not in headers:
            raise RuntimeError("Coluna obrigatória 'PAE' não encontrada.")

        pae_col = headers.index("PAE") + 1
        result = {}
        for idx, row in enumerate(values[1:], start=2):  # a partir da linha 2
            pae_val = row[pae_col-1].strip() if len(row) >= pae_col else ""
            if pae_val:
                result[idx] = pae_val
        return result

    def update_row_by_headers(self, row_idx: int, data: dict):
        # Garante que todos os headers existam e pega índices
        update_pairs = []
        for key, value in data.items():
            col_idx = self.header_index(key)
            update_pairs.append((col_idx, value))

        # 'Última atualização' sempre agora
        col_idx_last = self.header_index("Última atualização")
        update_pairs.append((col_idx_last, datetime.now().strftime("%Y-%m-%d %H:%M:%S")))

        # Monta linha atual completa para minimizar chamadas
        headers = self.ws.row_values(1)
        current = self.ws.row_values(row_idx)
        row_full = current + [""] * (len(headers) - len(current))

        for col_idx, value in update_pairs:
            # gspread espera array 2D para update de célula única? Vamos fazer update range da linha inteira no final
            row_full[col_idx-1] = value

        self.ws.update(f"{row_idx}:{row_idx}", [row_full])
