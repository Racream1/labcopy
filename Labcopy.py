from flask import Flask, render_template_string, request
from werkzeug.utils import secure_filename
import PyPDF2
import re
import io
import traceback

app = Flask(__name__)
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024

EXAMES_LISTA = [
    'pH', 'pCO2', 'pO2', 'BE', 'HCO3', 'Saturação de O2', 'FIO2', 'P/F',
    'Lactato', 'Hemoglobina', 'Hematócrito', 'Leucócitos', 'Bastonetes',
    'Mielócitos', 'Metamielócitos', 'Plaquetas', 'DOSAGEM DE URÉIA',
    'DOSAGEM DE CREATININA', 'DOSAGEM DE PROTEÍNA C REATIVA', 'DOSAGEM DE SÓDIO',
    'DOSAGEM DE POTÁSSIO', 'DOSAGEM DE CLORETOS', 'DOSAGEM DE MAGNÉSIO',
    'DOSAGEM DE CÁLCIO IÔNICO', 'DOSAGEM DE FÓSFORO', 'DOSAGEM DE TGO (AST)',
    'DOSAGEM DE TGP (ALT)', 'Bilirrubina total', 'Bilirrubina Direta',
    'Bilirrubina Indireta', 'Atividade', 'RNI', 'Tempo (TTPA)',
    'Relação (Paciente/Normal)', 'DOSAGEM DE CPK', 'Proteínas Totais',
    'Albumina', 'DOSAGEM DE FOSFATASE ALCALINA', 'DOSAGEM DE GAMA GT',
    'Dosagem de Amilase', 'DOSAGEM DE LIPASE', 'FIBRINOGÊNIO', 'CKMB',
    'Troponina', 'DOSAGEM DE VANCOMICINA', 'DOSAGEM DE TRIGLICÉRIDES', 'DHL'
]

def process_value(exame, valor):
    if exame in ['Plaquetas', 'Leucócitos']:
        # Remove caracteres não numéricos e converte para float
        cleaned = re.sub(r'[^\d,]', '', valor).replace(',', '.')
        try:
            multiplied = float(cleaned) * 1000
            return f"{multiplied:.0f}" if multiplied.is_integer() else f"{multiplied:.2f}"
        except:
            return valor
    return valor

def extract_exam_data(pdf_stream):
    try:
        reader = PyPDF2.PdfReader(pdf_stream)
        text = '\n'.join([page.extract_text() or '' for page in reader.pages])
        
        exam_data = {exame: '' for exame in EXAMES_LISTA}
        
        valor_pattern = r'[\d.,]+[\s]*(?:%|\))?'
        
        for exame in EXAMES_LISTA:
            if exame.startswith('DOSAGEM'):
                pattern = re.compile(
                    rf'{re.escape(exame)}.*?Resultado:\s*({valor_pattern})',
                    re.IGNORECASE | re.UNICODE | re.DOTALL
                )
            else:
                pattern = re.compile(
                    rf'{re.escape(exame)}\s*[:]?\s*({valor_pattern})',
                    re.IGNORECASE | re.UNICODE
                )
            
            match = pattern.search(text)
            if match:
                valor = match.group(1).strip()
                if '%' in valor:
                    valor = valor.replace(' ', '')
                
                if exame in ['Leucócitos', 'Plaquetas'] and valor:
                    cleaned_valor = re.sub(r'[^\d.,]', '', valor)
                    cleaned_valor = cleaned_valor.replace('.', '')  # Remove thousand separators
                    cleaned_valor = cleaned_valor.replace(',', '.')  # Convert comma to decimal point
                    if cleaned_valor:
                        try:
                            number = float(cleaned_valor)
                            multiplied = number * 1000
                            if multiplied.is_integer():
                                valor = str(int(multiplied))
                            else:
                                valor = "{:.2f}".format(multiplied).replace('.', ',')
                        except ValueError:
                            pass  # Keep original value if conversion fails
                
                exam_data[exame] = valor
        
        valores_absolutos_pattern = re.compile(
            r'Valores Absolutos\s*([\d.,]+)',
            re.IGNORECASE | re.UNICODE
        )
        valores_absolutos_match = valores_absolutos_pattern.findall(text)
        if valores_absolutos_match:
            for i, valor in enumerate(valores_absolutos_match):
                if i < len(EXAMES_LISTA):
                    exam_data[EXAMES_LISTA[i]] = valor.replace(',', '.').strip()
        
        return exam_data

    except Exception as e:
        raise RuntimeError(f"Erro na extração: {str(e)}")

@app.route('/', methods=['GET', 'POST'])
def main_route():
    if request.method == 'POST':
        if 'file' not in request.files:
            return render_template_string('''
                <div style="color: red;">Nenhum arquivo enviado!</div>
                <a href="/">Voltar</a>
            ''')
            
        file = request.files['file']
        if file.filename == '':
            return render_template_string('''
                <div style="color: red;">Arquivo inválido!</div>
                <a href="/">Voltar</a>
            ''')
            
        if file and file.filename.lower().endswith('.pdf'):
            try:
                pdf_stream = io.BytesIO(file.read())
                result = extract_exam_data(pdf_stream)
                
                table_rows = []
                valores_only = []
                for exame in EXAMES_LISTA:
                    valor = result.get(exame, '')
                    table_rows.append(f'<tr><td>{exame}</td><td>{valor}</td></tr>')
                    valores_only.append(valor if valor else '')
                
                return render_template_string('''
                    <html>
                    <head>
                        <style>
                            table { border-collapse: collapse; width: 80%; margin: 20px auto; }
                            td, th { border: 1px solid #ddd; padding: 8px; text-align: left; }
                            button { margin: 10px; padding: 8px 15px; cursor: pointer; }
                        </style>
                        <script>
                            function copiarValores() {
                                const valores = `{{ valores|join('\\n') }}`;
                                navigator.clipboard.writeText(valores)
                                    .then(() => alert('Valores copiados!'))
                                    .catch(err => console.error('Erro ao copiar:', err));
                            }
                        </script>
                    </head>
                    <body>
                        <button onclick="copiarValores()">Copiar Valores</button>
                        <table>
                            <tr><th>Exame</th><th>Resultado</th></tr>
                            {% for row in rows %}
                                {{ row|safe }}
                            {% endfor %}
                        </table>
                        <a href="/" style="display: block; text-align: center;">Nova análise</a>
                    </body>
                    </html>
                ''', rows=table_rows, valores=valores_only)
                
            except Exception as e:
                return render_template_string('''
                    <div style="color: red; margin:20px">ERRO: {{ error }}</div>
                    <a href="/">Voltar</a>
                ''', error=str(e))
                
        return render_template_string('''
            <div style="color: red;">Formato não suportado!</div>
            <a href="/">Voltar</a>
        ''')
    
    return render_template_string('''
        <!DOCTYPE html>
        <html>
        <body style="margin: 50px auto; max-width: 800px">
            <form method="POST" enctype="multipart/form-data" style="text-align: center">
                <input type="file" name="file" accept=".pdf" required 
                    style="margin: 20px; padding: 10px; border: 2px dashed #ccc">
                <br>
                <button type="submit" 
                    style="background: #2196F3; color: white; padding: 12px 24px; border: none; cursor: pointer">
                    Analisar PDF
                </button>
            </form>
        </body>
        </html>
    ''')

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=False)