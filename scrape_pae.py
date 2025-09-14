import os
import time
from typing import Optional, Dict
from dotenv import load_dotenv
from playwright.sync_api import sync_playwright

# === Ajuste estes seletores conforme o PAE 4.0 real ===
SELECTORS = {
    "cpf_input": 'input[name="j_username"], input[name="login"], #username, input[autocomplete="username"]',
    "senha_input": 'input[type="password"], input[name="j_password"], #password',
    "entrar_button": 'button:has-text("Entrar"), button:has-text("Login"), input[type="submit"]',
    # Depois do login (portal Governo Digital)
    "pae40_card": 'a:has-text("PAE 4.0"), a[title*="PAE 4.0"]',
    # Menu/consulta
    "menu_consultar_tramitados": 'a[title*="Consultar processos tramitados"], a:has-text("Consultar processos tramitados")',
    "campo_pesquisa_protocolo": 'input[placeholder*="Protocolo"], input[name*="protocolo"], input[aria-label*="Protocolo"]',
    "botao_buscar": 'button:has-text("Buscar"), button:has-text("Pesquisar"), button:has-text("Consultar")',
    # Resultados/detalhes
    "primeiro_resultado": 'table tr >> nth=1, .ui-datatable-tablewrapper tbody tr:first-child',
    # Campos de interesse (ajustar estratégia conforme DOM real)
    "campo_objeto": 'text=Objeto',
    "campo_rito": 'text=Rito, text=Modalidade, text=Tipo',
    "campo_etapa": 'text=Etapa',
    "campo_setor": 'text=Setor, text=Unidade',
    "campo_valor": 'text=Valor, text=R$',
    "campo_situacao": 'text=Situação, text=Status',
}

def is_truthy(val: Optional[str]) -> bool:
    return bool(val and str(val).strip())

def safe_inner_text(el):
    try:
        return el.inner_text().strip()
    except Exception:
        return ""

class PAEClient:
    def __init__(self):
        load_dotenv()
        self.base_url = "https://www.sistemas.pa.gov.br/governodigital/public/main/index.xhtml"
        self.cpf = os.environ["PAE_CPF"]
        self.senha = os.environ["PAE_SENHA"]
        self.headless = os.getenv("HEADLESS", "true").lower() == "true"

    def fetch_process_data(self, pae_number: str) -> Optional[Dict[str, str]]:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=self.headless)
            context = browser.new_context()
            page = context.new_page()
            page.set_default_timeout(30000)  # 30s

            try:
                page.goto(self.base_url)

                # Login
                page.wait_for_load_state("load")
                page.fill(SELECTORS["cpf_input"], self.cpf)
                page.fill(SELECTORS["senha_input"], self.senha)
                page.click(SELECTORS["entrar_button"])

                # Espera o portal carregar
                page.wait_for_load_state("networkidle")

                # Entrar no PAE 4.0
                try:
                    page.click(SELECTORS["pae40_card"])
                except Exception:
                    # Se o PAE abre em nova aba/iframe, adapte aqui
                    pass

                page.wait_for_load_state("networkidle")

                # Abrir consulta tramitados
                try:
                    page.click(SELECTORS["menu_consultar_tramitados"])
                except Exception:
                    # Talvez precise abrir o menu lateral primeiro — ajustar conforme DOM
                    pass

                # Pesquisar pelo número do protocolo
                page.wait_for_timeout(1000)
                page.fill(SELECTORS["campo_pesquisa_protocolo"], pae_number)
                page.click(SELECTORS["botao_buscar"])
                page.wait_for_load_state("networkidle")
                page.wait_for_timeout(1500)

                # Abrir primeiro resultado (se necessário)
                try:
                    page.click(SELECTORS["primeiro_resultado"])
                    page.wait_for_timeout(1200)
                except Exception:
                    pass

                # Estratégia simplificada: coletar textos do container principal
                content_text = page.inner_text("body")

                def find_value(labels):
                    # Busca heurística simples: acha a label e pega alguns chars após
                    for label in labels:
                        idx = content_text.lower().find(label.lower())
                        if idx != -1:
                            snippet = content_text[idx: idx+300]
                            return snippet.split("\n", 1)[-1].strip()[:200]
                    return ""

                objeto = find_value(["Objeto"])
                rito = find_value(["Rito", "Modalidade", "Tipo"])
                etapa = find_value(["Etapa"])
                setor = find_value(["Setor", "Unidade"])
                valor = find_value(["Valor", "R$"])
                situacao = find_value(["Situação", "Status"])

                data = {
                    "PAE": pae_number,
                    "Objeto": objeto,
                    "Rito / Modalidade": rito,
                    "Etapa atual": etapa,
                    "Dias na etapa": "",  # TODO: calcular se houver datas expostas
                    "Setor atual": setor,
                    "Valor": valor,
                    "Situação": situacao,
                    "Link PAE": page.url
                }

                # Se quiser filtrar apenas compras públicas:
                if not self.is_compra_publica(data):
                    # Retorne um dicionário mínimo, ou None para ignorar
                    # Aqui vamos retornar os dados mesmo assim, para transparência
                    pass

                return data

            except Exception as e:
                print(f"[ERRO] {e}")
                return None
            finally:
                context.close()
                browser.close()

    def is_compra_publica(self, data: Dict[str, str]) -> bool:
        texto = " ".join([str(v) for v in data.values()]).lower()
        keywords = [
            "licitação", "pregão", "dispensa", "inexigibilidade",
            "ata de registro", "arp", "srp", "adesão", "contrato", "compra", "aquisição"
        ]
        return any(k in texto for k in keywords)
