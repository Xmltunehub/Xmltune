import requests
import gzip
from lxml import etree
from datetime import datetime, timedelta

# Fazer download do EPG original
url = "https://epgshare01.online/epgshare01/epg_ripper_PT1.xml.gz"
r = requests.get(url)
with open("epg_ripper_PT1.xml.gz", "wb") as f:
    f.write(r.content)

# Descomprimir o XML
with gzip.open("epg_ripper_PT1.xml.gz", "rb") as f:
    tree = etree.parse(f)

root = tree.getroot()

# Função para somar 1 minuto e 1 segundo
def ajustar_tempo(valor):
    dt = datetime.strptime(valor, "%Y%m%d%H%M%S %z")
    dt += timedelta(minutes=1, seconds=1)
    return dt.strftime("%Y%m%d%H%M%S %z")

# Corrigir tempos dos <programme>
for prog in root.findall("programme"):
    prog.attrib["start"] = ajustar_tempo(prog.attrib["start"])
    prog.attrib["stop"] = ajustar_tempo(prog.attrib["stop"])

# Guardar o XML corrigido
with open("epg_corrigido.xml", "wb") as f:
    tree.write(f, encoding="utf-8", xml_declaration=True)

# Comprimir o XML corrigido para .gz
with open("epg_corrigido.xml", "rb") as f_in:
    with gzip.open("epg_corrigido.xml.gz", "wb") as f_out:
        f_out.writelines(f_in)

# Forçar alteração num ficheiro para garantir commit
with open("forcar_commit.txt", "a") as f:
    f.write(f"Atualizado em {datetime.now()}\n")

print("EPG corrigido e comprimido com sucesso.")
