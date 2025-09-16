# Scraper Médico

Projeto que utiliza Selenium e BeautifulSoup para buscar contatos de médicos no Bing.

## Pré-requisitos

1. Instalar o Python 3.11+ no Windows, marcando a opção "Add Python to PATH" na instalação.
2. Clonar o repositório:
   ```
   git clone https://github.com/seu-repo/scraper-medico.git
   cd scraper-medico
   ```

## Instalação

Na pasta do projeto, execute no Prompt de Comando ou PowerShell:
```
python -m pip install -r requirements.txt
```
Se o comando `python` não funcionar, use:
```
py -m pip install -r requirements.txt
```

## Estrutura do projeto

- `selenium_scraper.py`: Script principal.
- `names.csv`: Arquivo de entrada com nomes e cidades (colunas: name, city).
- `output_from_bing_headless.csv`: Arquivo de saída com telefones e flag de Instagram.
- `requirements.txt`: Dependências do projeto.

## Execução

Para rodar o scraper:
```
python selenium_scraper.py
```
Ou:
```
py selenium_scraper.py
```

## Funcionamento

1. Lê nomes e cidades do arquivo `names.csv`.
2. Realiza buscas no Bing com a query: "NOME CIDADE contato telefone consultório".
3. Abre até 4 resultados por busca.
4. Identifica resultados do Instagram e marca no CSV.
5. Extrai números de telefone das páginas, quando disponíveis.
6. Salva os resultados em `output_from_bing_headless.csv`.
```
