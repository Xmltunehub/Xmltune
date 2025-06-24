import requests
import gzip
from lxml import etree
from datetime import datetime, timedelta

# Fazer download da fonte original
url = "https://epgshare01.online/epgshare01/epg_ripper_PT1.xml.gz"
r = requests.get(url)
with open("origem.xml.gz", "wb") as f:
    f.write(r.content)

# Descomprimir o XML
with gzip.open("origem.xml.gz", "rb") as f:
    tree = etree.parse(f)

root = tree.getroot()

# Função para ajustar o tempo
def ajustar_tempo(valor):
    dt = datetime.strptime(valor, "%Y%m%d%H%M%S %z")
    dt += timedelta(minutes=1, seconds=1)
    return dt.strftime("%Y%m%d%H%M%S %z")

# Ajustar tempos dos programas
for prog in root.findall("programme"):
    prog.attrib["start"] = ajustar_tempo(prog.attrib["start"])
    prog.attrib["stop"] = ajustar_tempo(prog.attrib["stop"])

# Guardar o XML final
with open("compilacao.xml", "wb") as f:
    tree.write(f, encoding="utf-8", xml_declaration=True)

# Comprimir o XML
with open("compilacao.xml", "rb") as f_in:
    with gzip.open("compilacao.xml.gz", "wb") as f_out:
        f_out.writelines(f_in)

# Forçar alteração para commit
with open("forcar_commit.txt", "a") as f:
    f.write(f"Atualizado em {datetime.now()}\n")

print("Compilação concluída com sucesso.")
