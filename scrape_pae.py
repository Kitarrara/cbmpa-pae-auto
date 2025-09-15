import os
import re
from typing import Optional, Dict
from dotenv import load_dotenv
from playwright.sync_api import sync_playwright

# === Seletores genéricos e alternativas; ajustaremos depois com base nos artefatos ===
SELECTORS = {
    "cpf_input": 'input[name="j_username"], input[name="login"], #username, input[autocomplete="username"], input[type="text"]:below(:text("CPF"))',
    "senha_input": 'input[type="password"], input[name="j_password"], #password',
    "entrar_button": 'button:has-text("Entrar"), button:has-text("Login"), input[type="submit"]',
    "pae40_card": 'a:has-text("PAE 4.0"), a[title*="PAE 4.0"]',
    "menu_consultar_tramitados": 'a[title*="Consultar processos tramitados"], a:has-text("Consultar processos tramitados"), [role="menuitem"]:has-text("Tramitados")',
    "campo_pesquisa_protocolo": 'input[placeholder*="Protocolo"], input[name*="protocolo"], input[aria-label*="Protocolo"], input[type="search"]',
    "botao_buscar": 'button:has-text("Buscar"), button:has-text("Pesquisar"), button:has-text("Consultar")',
    "primeiro_resultado": 'table tr >> nth=1, .ui-datatable-tablewrapper tbody tr:first-child, tbody tr[data-ri="0"]'
}

LABELS = {
    "Objeto": ["Objeto"],
    "Rito / Modalidade": ["Rito", "Modalidade", "Tipo"],
    "Etapa atual": ["Etapa", "Fase atual"],
    "Dias na etapa": [],  # calcularemos depois se houver datas
    "Setor atual": ["Setor", "Unidade", "Órgão"],
    "Valor": ["Valor", "R$"],
    "Situação": ["Situação", "Status"]
}

def _sanitize_filename(s: str) -> str:
    return re.sub(r'[^a-zA-Z0-9_.-]+', "_", s)

def _find_after_label_text(page_text: str, labels):
    """
    Heurística simples: procura uma label e captura o texto imediatamente após (quebra de linha).
    """
    low = page_text.lower()
    for label in labels:
        i = low.find(label.lower())
        if i != -1:
            snippet = page_text[i:i+400]
            # pega a parte após a 1ª quebra de linha
            return snippet.split("\n", 1)[-1].strip()[:300]
    return ""

def _kv_from_html(page_html: str, labels):
    """
    Outra heurística: procura <th>Label</th><td>Valor</td> ou label: valor
    """
    for label in labels:
        # th/td
        m = re.search(rf"<th[^>]*>\s*{re.escape(label)}\s*</th>\s*<td[^>]*>(.*?)</td>", page_html, re.IGNORECASE|re.DOTALL)
        if m:
            return re.sub(r"<[^>]+>", " ", m.group(1)).strip()
        # label: valor
        m2 = re.search(rf"{re.escape(label)}\s*[:\-]\s*(.+?)<", page_html, re.IGNORECASE|re.DOTALL)
        if m2:
            return re.sub(r"<[^>]+>", " ", m2.group(1)).strip()
    return ""

class PAEClient:
    def __init__(self):
        load_dotenv()
        self.base_url = "https://www.sistemas.pa.gov.br/governodigital/public/main/index.xhtml"
        self.cpf = os.environ["PAE_CPF"]
        self.senha = os.environ["PAE_SENHA"]
        self.headless = os.getenv("HEADLESS", "true").lower() == "true"
        self.artifacts_dir = "artifacts"
        os.makedirs(self.artifacts_dir, exist_ok=True)

    def fetch_process_data(self, pae_number: str) -> Optional[Dict[str, str]]:
        safe = _sanitize_filename(pae_number)

        with sync_playwright() as p:
            browser = p.chromium.launch(headless=self.headless, args=["--disable-gpu"])
            context = browser.new_context()
            page = context.new_page()
            page.set_default_timeout(45000)  # 45s

            try:
                page.goto(self.base_url)
                page.wait_for_load_state("load")

                # Login
                try:
                    page.fill(SELECTORS["cpf_input"], self.cpf)
                    page.fill(SELECTORS["senha_input"], self.senha)
                    page.click(SELECTORS["entrar_button"])
                except Exception:
                    pass  # alguns logins podem estar automaticamente autenticados (SSO)

                page.wait_for_load_state("networkidle")

                # Entrar no PAE 4.0
                try:
                    page.click(SELECTORS["pae40_card"])
                    page.wait_for_load_state("networkidle")
                except Exception:
                    pass

                # Ir para "Consultar processos tramitados"
                try:
                    page.click(SELECTORS["menu_consultar_tramitados"])
                    page.wait_for_load_state("networkidle")
                except Exception:
                    pass

                # Buscar o protocolo
                page.wait_for_timeout(1200)
                page.fill(SELECTORS["campo_pesquisa_protocolo"], pae_number)
                page.click(SELECTORS["botao_buscar"])
                page.wait_for_load_state("networkidle")
                page.wait_for_timeout(1500)

                # Abrir primeiro resultado (quando há lista)
                try:
                    page.click(SELECTORS["primeiro_resultado"])
                    page.wait_for_timeout(1200)
                except Exception:
                    pass

                # Captura artefatos para debug
                html = page.content()
                with open(os.path.join(self.artifacts_dir, f"{safe}.html"), "w", encoding="utf-8") as f:
                    f.write(html)
                page.screenshot(path=os.path.join(self.artifacts_dir, f"{safe}.png"), full_page=True)

                # Estratégias de extração
                body_text = page.inner_text("body")

                data = {"PAE": pae_number, "Link PAE": page.url}

                for k, labels in LABELS.items():
                    val = ""
                    if labels:
                        # 1) tenta por HTML (th/td, label:valor)
                        val = _kv_from_html(html, labels)
                        # 2) fallback: busca por texto após a label
                        if not val:
                            val = _find_after_label_text(body_text, labels)
                    else:
                        val = ""  # "Dias na etapa" calcularemos depois
                    data[k] = val.strip()

                return data

            except Exception as e:
                print(f"[ERRO] {e}")
                # Mesmo em erro, tente salvar um print para debug
                try:
                    page.screenshot(path=os.path.join(self.artifacts_dir, f"{safe}_ERROR.png"), full_page=True)
                except Exception:
                    pass
                return None
            finally:
                context.close()
                browser.close()
