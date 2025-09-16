# Scraper Médico

Projeto que utiliza Selenium e BeautifulSoup para buscar contatos de médicos no Bing.

## Pré-requisitos

1. **Instalar o [Python 3.11+](https://www.python.org/downloads/)**  
   Durante a instalação, marque a opção **"Add Python to PATH"**.
2. **Clonar este repositório**:
   ```bash
   git clone https://github.com/seu-repo/scraper-medico.git
   cd scraper-medico

Instalação das dependências

No Prompt de Comando ou PowerShell, dentro da pasta do projeto, execute:

python -m pip install -r requirements.txt

Se o comando python não funcionar, use:

py -m pip install -r requirements.txt

Estrutura do projeto

    selenium_scraper.py — Script principal que executa o scraper

    names.csv — Lista de entrada com nomes e cidades (colunas: name, city)

    output_from_bing_headless.csv — Saída com telefone e flag de Instagram

    requirements.txt — Dependências do projeto

Execução

Para rodar o scraper:

python selenium_scraper.py

ou

py selenium_scraper.py

Funcionamento

    Lê os nomes e cidades do arquivo names.csv.

    Faz buscas no Bing com a query: "NOME CIDADE contato telefone consultório".

    Abre até 4 resultados de cada busca.

    Se algum resultado for do Instagram, marca essa informação no CSV.

    Extrai números de telefone das páginas quando possível.

    Salva os resultados em output_from_bing_headless.csv.

Dependências

O projeto usa as seguintes bibliotecas Python (listadas em requirements.txt):

selenium
webdriver-manager
beautifulsoup4
phonenumbers
