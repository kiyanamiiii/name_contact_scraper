<!doctype html>
<html lang="pt-BR">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width,initial-scale=1">
  <style>body{font-family:Inter,Arial,sans-serif;margin:24px;color:#111}h1{font-size:22px}pre{background:#f8f8f8;padding:10px;border-radius:6px}</style>
</head>
<body>
  <h1>Scraper WhatsApp — Resumo mínimo</h1>
  <p>Objetivo: extrair números públicos de médicos a partir de <code>names.csv</code> e gerar <code>output_clean.csv</code> (name,city,number). Um <code>debug_output.csv</code> contém fonte e metadados.</p>

  <h2>Passos rápidos</h2>
  <ol>
    <li>Crie virtualenv e ative.</li>
    <li>Instale dependências: <code>pip install -r requirements.txt</code>.</li>
    <li>Edite <code>.env.sample</code> e salve como <code>.env</code> se quiser configurar via variáveis.</li>
    <li>Coloque <code>names.csv</code> com cabeçalho <code>name,city</code>.</li>
    <li>Rode: <code>python optimized_whatsapp_scraper.py</code>.</li>
    <li>Revise <code>debug_output.csv</code> antes de procesar lote completo.</li>
  </ol>

  <h2>Formato entrada</h2>
  <pre>name,city
"Dr. João Silva","Porto Alegre"</pre>

  <h2>Arquivos gerados</h2>
  <ul>
    <li><code>output_clean.csv</code> — final (name,city,number).</li>
    <li><code>debug_output.csv</code> — auditoria (source_url, raw_match, method, wa_quick, twochat).</li>
  </ul>

  <h2>Observações essenciais</h2>
  <ul>
    <li>Mantenha <code>HEADLESS=True</code> no script para rodar sem GUI.</li>
    <li>Teste em 1% do dataset e revise <code>debug_output.csv</code>.</li>
    <li>Para validação definitiva do WhatsApp use API oficial (2chat/WhatsApp Business).</li>
  </ul>

  <h2>Comandos úteis</h2>
  <pre>python -m venv venv
# Linux/mac
source venv/bin/activate
# Windows
venv/Scripts/activate
pip install -r requirements.txt
python optimized_whatsapp_scraper.py</pre>

</body>
</html>
