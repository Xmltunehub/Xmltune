import requests
import gzip
import os
import shutil
from lxml import etree
from datetime import datetime, timedelta
import logging

# Configurar logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def limpar_ficheiros_temporarios():
    """Remove ficheiros temporários"""
    ficheiros_temp = ["origem.xml.gz", "origem.xml", "compilacao.xml"]
    for ficheiro in ficheiros_temp:
        if os.path.exists(ficheiro):
            try:
                os.remove(ficheiro)
                logger.info(f"Ficheiro temporário {ficheiro} removido")
            except Exception as e:
                logger.warning(f"Não foi possível remover {ficheiro}: {e}")

def fazer_download():
    """Faz download do ficheiro EPG original"""
    url = "https://epgshare01.online/epgshare01/epg_ripper_PT1.xml.gz"
    
    try:
        logger.info("🔄 Iniciando download do EPG...")
        
        # Request com timeout e headers
        headers = {
            'User-Agent': 'Mozilla/5.0 (compatible; EPG-Processor/1.0)'
        }
        
        r = requests.get(url, headers=headers, timeout=60, stream=True)
        r.raise_for_status()
        
        # Guardar ficheiro
        with open("origem.xml.gz", "wb") as f:
            for chunk in r.iter_content(chunk_size=8192):
                f.write(chunk)
        
        # Verificar tamanho
        tamanho = os.path.getsize("origem.xml.gz")
        logger.info(f"✅ Download concluído. Tamanho: {tamanho:,} bytes")
        
        if tamanho < 1000:
            raise Exception("Ficheiro muito pequeno - possivelmente corrompido")
            
        return True
        
    except Exception as e:
        logger.error(f"❌ Erro no download: {e}")
        return False

def descomprimir_xml():
    """Descomprime o ficheiro XML"""
    try:
        logger.info("🔄 A descomprimir XML...")
        
        with gzip.open("origem.xml.gz", "rb") as f_in:
            with open("origem.xml", "wb") as f_out:
                shutil.copyfileobj(f_in, f_out)
        
        # Verificar se foi descomprimido
        if not os.path.exists("origem.xml"):
            raise Exception("Ficheiro XML não foi criado")
            
        tamanho = os.path.getsize("origem.xml")
        logger.info(f"✅ Descompressão concluída. Tamanho XML: {tamanho:,} bytes")
        return True
        
    except Exception as e:
        logger.error(f"❌ Erro na descompressão: {e}")
        return False

def processar_xml():
    """Processa o XML aplicando +1 minuto e 1 segundo"""
    try:
        logger.info("🔄 A processar XML...")
        
        # Parse do XML
        parser = etree.XMLParser(recover=True)
        with open("origem.xml", "rb") as f:
            tree = etree.parse(f, parser)
        
        root = tree.getroot()
        
        # Contar programas processados
        programas_processados = 0
        programas_com_erro = 0
        
        # Processar cada programa
        for prog in root.findall("programme"):
            try:
                if "start" in prog.attrib:
                    prog.attrib["start"] = ajustar_tempo(prog.attrib["start"])
                
                if "stop" in prog.attrib:
                    prog.attrib["stop"] = ajustar_tempo(prog.attrib["stop"])
                
                programas_processados += 1
                
            except Exception as e:
                programas_com_erro += 1
                logger.warning(f"Erro ao processar programa {prog.get('start', 'unknown')}: {e}")
        
        logger.info(f"✅ Processamento concluído:")
        logger.info(f"   - Programas processados: {programas_processados}")
        logger.info(f"   - Programas com erro: {programas_com_erro}")
        
        # Guardar XML processado
        with open("compilacao.xml", "wb") as f:
            tree.write(f, encoding="utf-8", xml_declaration=True, pretty_print=True)
        
        return True
        
    except Exception as e:
        logger.error(f"❌ Erro no processamento XML: {e}")
        return False

def ajustar_tempo(valor_tempo):
    """Ajusta o tempo adicionando 1 minuto e 1 segundo"""
    try:
        # Formato esperado: YYYYMMDDHHMMSS +TZTZ
        if len(valor_tempo) >= 14:
            # Separar data/hora do timezone
            parte_data = valor_tempo[:14]
            parte_timezone = valor_tempo[14:].strip()
            
            # Converter para datetime
            dt = datetime.strptime(parte_data, "%Y%m%d%H%M%S")
            
            # Adicionar 1 minuto e 1 segundo
            dt += timedelta(minutes=1, seconds=1)
            
            # Reconstruir string
            nova_data = dt.strftime("%Y%m%d%H%M%S")
            return f"{nova_data} {parte_timezone}" if parte_timezone else nova_data
            
    except Exception as e:
        logger.warning(f"Erro ao ajustar tempo '{valor_tempo}': {e}")
        
    return valor_tempo  # Retorna original se houver erro

def comprimir_xml():
    """Comprime o XML final"""
    try:
        logger.info("🔄 A comprimir ficheiro final...")
        
        with open("compilacao.xml", "rb") as f_in:
            with gzip.open("compilacao.xml.gz", "wb") as f_out:
                shutil.copyfileobj(f_in, f_out)
        
        # Verificar ficheiro comprimido
        tamanho_final = os.path.getsize("compilacao.xml.gz")
        logger.info(f"✅ Compressão concluída. Tamanho final: {tamanho_final:,} bytes")
        
        return True
        
    except Exception as e:
        logger.error(f"❌ Erro na compressão: {e}")
        return False

def main():
    """Função principal"""
    logger.info("🚀 Iniciando processamento EPG...")
    
    try:
        # 1. Limpar ficheiros temporários
        limpar_ficheiros_temporarios()
        
        # 2. Fazer download
        if not fazer_download():
            logger.error("❌ Falha no download - processo abortado")
            return False
        
        # 3. Descomprimir
        if not descomprimir_xml():
            logger.error("❌ Falha na descompressão - processo abortado")
            return False
        
        # 4. Processar XML
        if not processar_xml():
            logger.error("❌ Falha no processamento - processo abortado")
            return False
        
        # 5. Comprimir resultado final
        if not comprimir_xml():
            logger.error("❌ Falha na compressão - processo abortado")
            return False
        
        # 6. Limpar ficheiros temporários
        limpar_ficheiros_temporarios()
        
        logger.info("🎉 Processo concluído com sucesso!")
        logger.info(f"📁 Ficheiro final: compilacao.xml.gz")
        
        return True
        
    except Exception as e:
        logger.error(f"❌ Erro geral no processamento: {e}")
        limpar_ficheiros_temporarios()
        return False

if __name__ == "__main__":
    sucesso = main()
    exit(0 if sucesso else 1)
