import requests
import gzip
import os
from lxml import etree
from datetime import datetime, timedelta

# Remover ficheiros antigos se existirem
ficheiros_a_apagar = ["origem.xml.gz", "compilacao.xml", "compilacao.xml.gz"]
for ficheiro in ficheiros_a_apagar:
    if os.path.exists(ficheiro):
        os.remove(ficheiro)
        print(f"Ficheiro {ficheiro} removido com sucesso.")

# Fazer download do ficheiro original
url = "https://epgshare01.online/epgshare01/epg_ripper_PT1.xml.gz"
r = requests.get(url)
with open("origem.xml.gz", "wb") as f:
    f.write(r.content)

tamanho_ficheiro = os.path.getsize("origem.xml.gz")
print(f"Download concluído. Tamanho do ficheiro: {tamanho_ficheiro} bytes")

if tamanho_ficheiro < 1000:
    print("Erro: Ficheiro descarregado parece estar vazio ou incompleto. Processo abortado.")
    exit(1)

# Descomprimir o XML
with gzip.open("origem.xml.gz", "rb") as f:
    tree = etree.parse(f)
print("Descompressão concluída.")

root = tree.getroot()

# Função para ajustar o tempo
def ajustar_tempo(valor):
    dt = datetime.strptime(valor, "%Y%m%d%H%M%S %z")
    dt += timedelta(minutes=1, seconds=1)
    return dt.strftime("%Y%m%d%H%M%S %z")

# Ajustar tempos dos <programme>
for prog in root.findall("programme"):
    prog.attrib["start"] = ajustar_tempo(prog.attrib["start"])
    prog.attrib["stop"] = ajustar_tempo(prog.attrib["stop"])

# Guardar o ficheiro compilado
with open("compilacao.xml", "wb") as f:
    tree.write(f, encoding="utf-8", xml_declaration=True)
print("Ficheiro compilado guardado.")

# Comprimir o ficheiro compilado
with open("compilacao.xml", "rb") as f_in:
    with gzip.open("compilacao.xml.gz", "wb") as f_out:
        f_out.writelines(f_in)
print("Ficheiro comprimido com sucesso.")

# Forçar alteração para garantir commit
with open("forcar_commit.txt", "a") as f:
    f.write(f"Atualizado em {datetime.now()}\n")

print("Processo concluído com sucesso.")
