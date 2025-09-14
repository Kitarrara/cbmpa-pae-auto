# CBMPA — PAE 4.0 → Google Sheets Auto‑Updater

Automatiza a coleta de dados no **PAE 4.0** e atualiza a planilha do Google com o status dos processos de compra do **CBMPA**.

> **Fluxo:** GitHub Actions (agendado) → Playwright (login no PAE 4.0, coleta dados) → Google Sheets API (atualiza planilha).  
> **Importante:** Este projeto não depende de API oficial do PAE; ele usa **navegação real** (RPA) com navegador automatizado.

---

## O que ele faz

1. Lê da sua planilha os números de PAE (uma linha por processo).
2. Acessa o site do PAE 4.0, faz login com suas credenciais e pesquisa cada PAE.
3. Coleta campos úteis (ex.: Objeto, Rito/Modalidade, Etapa atual, Dias na etapa, Setor, Valor, Situação, etc.).
4. Atualiza as colunas correspondentes na planilha.

> Você pode rodar **localmente** ou em **GitHub Actions** no horário que quiser (ex.: de hora em hora).

---

## Requisitos

- **Python 3.10+**
- **Playwright** (instalado automaticamente via `pip install -r requirements.txt`; depois execute `playwright install`)
- Uma **Conta de Serviço** do Google com acesso de edição à sua planilha (compartilhe a planilha com o e‑mail da conta de serviço)
- Credenciais:
  - `PAE_CPF` e `PAE_SENHA` (credenciais pessoais do portal Governo Digital)
  - `SHEET_ID` → ID da sua planilha (o que está entre `/d/` e `/edit` no link)
  - `SHEET_GID` → gid da aba (número após `gid=` no link); usaremos para localizar a folha via título também
  - `GOOGLE_SERVICE_ACCOUNT_JSON` → o JSON **inteiro** das credenciais da conta de serviço (colar em uma única variável de ambiente)

> **Segurança:** armazene essas informações como **Variáveis/Secrets** no GitHub (ou em `.env` local que não deve ser commitado).

---

## Instalação (local)

```bash
python -m venv .venv
. .venv/bin/activate  # Windows: .venv\Scripts\activate
pip install -r requirements.txt
playwright install
```

Crie um arquivo `.env` (veja `.env.example`) e preencha:

```ini
PAE_CPF=72204850268
PAE_SENHA=********
SHEET_ID=1PzJz3eU3qZ7viAxXm1OuMUg6j7rQyh0A9XM8E-QX7q0
SHEET_TAB_NAME=Processos 2025
SHEET_GID=2135472780
GOOGLE_SERVICE_ACCOUNT_JSON={ "type": "service_account", "...": "..." }
```

> **Compartilhe** a planilha com o e‑mail da conta de serviço antes de rodar (Permissão: Editor).

### Executar

```bash
python run.py
```

---

## Uso com GitHub Actions (agendado)

1. Crie um repositório no GitHub e envie estes arquivos.
2. Em **Settings → Secrets and variables → Actions → New repository secret**, crie estes **Secrets**:

   - `PAE_CPF`
   - `PAE_SENHA`
   - `SHEET_ID`
   - `SHEET_TAB_NAME` (ex.: `Processos 2025`)
   - `SHEET_GID` (ex.: `2135472780`)
   - `GOOGLE_SERVICE_ACCOUNT_JSON` (cole **o JSON completo** das credenciais)

3. O workflow em `.github/workflows/schedule.yml` já agenda para rodar **a cada 2 horas** (ajuste o CRON se quiser).

> O Playwright roda com `browser: chromium` no modo **headless**.

---

## Estrutura da Planilha esperada

A aba (ex.: *Processos 2025*) deve conter pelo menos estas colunas (em **qualquer ordem**):

- **PAE** (nº do processo, ex.: `E-2025/2893026`)
- **Objeto**
- **Rito / Modalidade**
- **Etapa atual**
- **Dias na etapa**
- **Setor atual**
- **Valor (estimado/homologado)**
- **Situação / Status**
- **Última atualização**

> O script detecta as colunas por **nome** e atualiza se encontrar correspondentes. Se alguma coluna faltar, ela será criada ao final.

---

## Ajustando os seletores do PAE

Como o PAE 4.0 é um sistema dinâmico, IDs e classes podem variar. O arquivo `scrape_pae.py` tem **seletores marcados** com `# TODO:`.  
Na **primeira execução**, se algo não for encontrado, o script loga um **print com sugestões** de como corrigir o seletor.

### Dica prática
Abra o PAE no navegador, pressione **F12** e inspecione:
- Campo CPF/Usuário
- Campo Senha
- Botão “Entrar”
- Link/ícone do **PAE 4.0**
- Menu “Consultar processos tramitados” (lupa sobre documento)
- Campo de busca por nº de protocolo
- Tabela/área de detalhes do processo
- Campos de interesse (Objeto, Etapa, Setor, etc.)

Depois ajuste as constantes em `scrape_pae.py` conforme necessário.

---

## Campos coletados (padrão)

- Objeto
- Rito/Modalidade
- Etapa atual
- Dias na etapa
- Setor atual / Unidade
- Valor estimado / homologado (se disponível)
- Situação/Status
- Link direto do processo (se houver URL estável)
- Data/hora da coleta (para “Última atualização”)

---

## Suporte a filtro por “somente compras”

Se quiser que o script **ignore** PAE que **não** sejam de compras públicas, ele tenta verificar por **palavras‑chave** (ex.: Licitação, Dispensa, ARP, SRP, Pregão, Adesão, Contrato).  
Ajuste a função `is_compra_publica()` em `scrape_pae.py` conforme a realidade do CBMPA.

---

## Logs e troubleshooting

- Use `LOG_LEVEL=DEBUG` no `.env` para mais detalhes.
- Em caso de bloqueios de bot, ative `headful` (não headless) em `run.py` para observar a navegação.
- Se houver CAPTCHA/2FA, será necessário intervenção manual ou whitelist.

---

## Licença

Uso interno do CBMPA.
