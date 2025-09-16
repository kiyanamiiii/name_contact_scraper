<!DOCTYPE html>
<html lang="pt-BR">
<head>
  <meta charset="UTF-8">
</head>
<body>
  <h1>Scraper Médico</h1>
  <p>Este projeto utiliza Selenium e BeautifulSoup para buscar contatos de médicos no Bing.</p>

  <h2>Funcionamento</h2>
  <ol>
    <li>Lê os nomes e cidades do arquivo <code>names.csv</code>.</li>
    <li>Executa buscas no Bing com a query: "NOME CIDADE contato telefone consultório".</li>
    <li>Abre até 4 resultados por busca.</li>
    <li>Extrai números de telefone encontrados nas páginas.</li>
    <li>Se algum dos resultados for do Instagram, marca essa informação no CSV.</li>
    <li>Os dados extraídos são salvos em <code>output_from_bing_headless.csv</code>.</li>
  </ol>

  <h2>Estrutura</h2>
  <ul>
    <li><code>selenium_scraper.py</code> - Script principal</li>
    <li><code>names.csv</code> - Lista de entrada com nomes e cidades</li>
    <li><code>output_from_bing_headless.csv</code> - Saída com telefone e flag de Instagram</li>
  </ul>

  <h2>Requisitos</h2>
  <ul>
    <li>Python 3.8 ou superior</li>
    <li>Bibliotecas: selenium, webdriver-manager, beautifulsoup4, phonenumbers</li>
  </ul>

  <h2>Execução</h2>
  <pre>
python selenium_scraper.py
  </pre>
</body>
</html>
