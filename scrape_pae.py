import os
import re
from typing import Optional, Dict
from dotenv import load_dotenv
from playwright.sync_api import sync_playwright

# =========================
# Seletores "genéricos"
# (vamos refinando depois com os artifacts)
# =========================
SELECTORS = {
    # Login no portal Governo Digital
    "cpf_input": 'input[name="j_username"], input[name="login"], #username, input[autocomplete="username"], input[type="text"]:below(:text("CPF"))',
    "senha_input": 'input[type="password"], input[name="j_password"], #password',
    "entrar_button": 'button:has-text("Entrar"), button:has-text("Login"), input[type="submit"]',

    # Acessar o app PAE 4.0 após login
    "pae40_card": 'a:has-text("PAE 4.0"), a[title*="PAE 4.0"]',

    # Menu/consulta de processos tramitados
    "menu_consultar_tramitados": 'a[title*="Consultar processos tramitados"], a:has-text("Consultar processos tramitados"), [role="menuitem"]:has-text("Tramitados")',

    # Busca por protocolo
    "campo_pesquisa_protocolo": 'input[placeholder*="Protocolo"], input[name*="protocolo"], input[aria-label*="Protocolo"], input[type="search"]',
    "botao_buscar": 'button:has-text("Buscar"), button:has-text("Pesquisar"), button:has-text("Consultar")',

    # Primeiro resultado (quando há tabela)
    "primeiro_resultado": 'table tr >> nth=1, .ui-datatable-tablewrapper tbody tr:first-child, tbody tr[data-ri="0"]',
}

# Labels-alvo (podem variar; ajustaremos depois com artifacts)
LABELS = {
    "Objeto": ["Objeto", "Assunto do Processo", "Assunto"],
    "Rito / Modalidade": ["Rito", "Modalidade", "Tipo"],
    "Etapa atual": ["Etapa", "Fase atual"],
    "Dias na etapa": [],  # calcularemos depois se houver datas
    "Setor atual": ["Setor", "Unidade", "Órgão"],
    "Valor": ["Valor", "R$"],
    "Situação": ["Situação", "Status"],
}

# ---------- utilidades ----------
def _sanitize_filename(s: str) -> str:
    return re.sub(r'[^a-zA-Z0-9_.-]+', "_", s)

def _find_after_label_text(page_text: str, labels):
    """
    Heurística simples: procura a label no texto e captura a linha imediatamente após.
    """
    low = page_text.lower()
    for label in labels:
        i = low.find(label.lower())
        if i != -1:
            snippet = page_text[i:i+400]
            return snippet.split("\n", 1)[-1].strip()[:300]
    return ""

def _kv_from_html(page_html: str, labels):
    """
    Procura pares chave-valor no HTML:
      <th>Label</th><td>Valor</td>  ou  'Label: Valor'
    """
    for label in labels:
        # th/td
        m = re.search(
            rf"<th[^>]*>\s*{re.escape(label)}\s*</th>\s*<td[^>]*>(.*?)</td>",
            page_html, re.IGNORECASE | re.DOTALL
        )
        if m:
            return re.sub(r"<[^>]+>", " ", m.group(1)).strip()

        # label: valor
        m2 = re.search(
            rf"{re.escape(label)}\s*[:\-]\s*(.+?)<",
            page_html, re.IGNORECASE | re.DOTALL
        )
        if m2:
            return re.sub(r"<[^>]+>", " ", m2.group(1)).strip()
    return ""

# ---------- cliente ----------
class PAEClient:
    def __init__(self):
        load_dotenv()
        self.base_url = "https://www.sistemas.pa.gov.br/governodigital/public/main/index.xhtml"
        self.cpf = os.environ["PAE_CPF"]
        self.senha = os.environ["PAE_SENHA"]
        self.headless = os.getenv("HEADLESS", "true").lower() == "true"

        # artifacts (prints/HTML) para debug
        self.artifacts_dir = "artifacts"
        os.makedirs(self.artifacts_dir, exist_ok=True)

        # timeouts mais folgados para runner do GitHub
        self.default_timeout = 120_000  # 120s

    def fetch_process_data(self, pae_number: str) -> Optional[Dict[str, str]]:
        safe = _sanitize_filename(pae_number)

        with sync_playwright() as p:
            browser = p.chromium.launch(
                headless=self.headless,
                args=["--disable-gpu"]
            )
            context = browser.new_context(
                user_agent=(
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/118 Safari/537.36"
                )
            )
            page = context.new_page()
            page.set_default_timeout(self.default_timeout)

            try:
                # 1) Abre portal (espera DOM pronto e tenta idle)
                page.goto(self.base_url, wait_until="domcontentloaded", timeout=self.default_timeout)
                try:
                    page.wait_for_load_state("networkidle", timeout=30_000)
                except Exception:
                    pass
                page.screenshot(path=os.path.join(self.artifacts_dir, f"{safe}_00_home.png"), full_page=True)

                # 2) Login (se campos existirem)
                try:
                    page.wait_for_selector(SELECTORS["cpf_input"], timeout=30_000)
                    page.fill(SELECTORS["cpf_input"], self.cpf)
                    page.fill(SELECTORS["senha_input"], self.senha)
                    page.click(SELECTORS["entrar_button"])
                    try:
                        page.wait_for_load_state("networkidle", timeout=30_000)
                    except Exception:
                        pass
                    page.screenshot(path=os.path.join(self.artifacts_dir, f"{safe}_01_after_login.png"), full_page=True)
                except Exception:
                    # talvez já esteja logado (SSO)
                    page.screenshot(path=os.path.join(self.artifacts_dir, f"{safe}_01_login_skipped.png"), full_page=True)

                # 3) Entrar no PAE 4.0
                try:
                    page.click(SELECTORS["pae40_card"], timeout=20_000)
                    try:
                        page.wait_for_load_state("networkidle", timeout=30_000)
                    except Exception:
                        pass
                except Exception:
                    pass
                page.screenshot(path=os.path.join(self.artifacts_dir, f"{safe}_02_pae40.png"), full_page=True)

                # 4) Consulta tramitados
                try:
                    page.click(SELECTORS["menu_consultar_tramitados"], timeout=20_000)
                    try:
                        page.wait_for_load_state("networkidle", timeout=30_000)
                    except Exception:
                        pass
                except Exception:
                    pass
                page.screenshot(path=os.path.join(self.artifacts_dir, f"{safe}_03_tramitados.png"), full_page=True)

                # 5) Buscar protocolo
                try:
                    page.fill(SELECTORS["campo_pesquisa_protocolo"], pae_number)
                    page.click(SELECTORS["botao_buscar"])
                    try:
                        page.wait_for_load_state("networkidle", timeout=30_000)
                    except Exception:
                        pass
                except Exception:
                    # se não achar campo/botão agora, mesmo assim salva estado e segue
                    page.screenshot(path=os.path.join(self.artifacts_dir, f"{safe}_03b_search_failed.png"), full_page=True)

                # 6) Abrir primeiro resultado (se houver tabela)
                try:
                    page.click(SELECTORS["primeiro_resultado"], timeout=10_000)
                    page.wait_for_timeout(1200)
                except Exception:
                    pass

                # 7) Captura HTML/print para debug e extração
                html = page.content()
                with open(os.path.join(self.artifacts_dir, f"{safe}.html"), "w", encoding="utf-8") as f:
                    f.write(html)
                page.screenshot(path=os.path.join(self.artifacts_dir, f"{safe}.png"), full_page=True)

                # 8) Extração (duas heurísticas: HTML e texto)
                body_text = page.inner_text("body")

                data = {
                    "PAE": pae_number,
                    "Link PAE": page.url,
                }

                for key, labels in LABELS.items():
                    if not labels:  # "Dias na etapa"
                        data[key] = ""
                        continue

                    val = _kv_from_html(html, labels)
                    if not val:
                        val = _find_after_label_text(body_text, labels)
                    data[key] = (val or "").strip()

                return data

            except Exception as e:
                print(f"[ERRO] {e}")
                # sempre salva algo para debug
                try:
                    page.screenshot(path=os.path.join(self.artifacts_dir, f"{safe}_ERROR.png"), full_page=True)
                except Exception:
                    pass
                return None
            finally:
                context.close()
                browser.close()
