import requests
import gzip
import os
import shutil
from lxml import etree
from datetime import datetime, timedelta
import logging
import sys

# Configurar logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def limpar_ficheiros_temporarios():
    """Remove ficheiros temporários"""
    ficheiros_temp = ["origem.xml.gz", "origem.xml"]
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
        
        # Request com timeout e headers melhorados
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'pt-PT,pt;q=0.9,en;q=0.8',
            'Accept-Encoding': 'gzip, deflate',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1'
        }
        
        # Tentar o download com retry
        max_tentativas = 3
        for tentativa in range(max_tentativas):
            try:
                logger.info(f"Tentativa {tentativa + 1}/{max_tentativas}")
                
                response = requests.get(url, headers=headers, timeout=120, stream=True)
                response.raise_for_status()
                
                # Guardar ficheiro
                total_size = 0
                with open("origem.xml.gz", "wb") as f:
                    for chunk in response.iter_content(chunk_size=8192):
                        if chunk:
                            f.write(chunk)
                            total_size += len(chunk)
                
                # Verificar tamanho
                tamanho = os.path.getsize("origem.xml.gz")
                logger.info(f"✅ Download concluído. Tamanho: {tamanho:,} bytes")
                
                if tamanho < 1000:
                    raise Exception("Ficheiro muito pequeno - possivelmente corrompido")
                
                # Verificar se é um ficheiro gzip válido
                try:
                    with gzip.open("origem.xml.gz", "rb") as test_file:
                        test_file.read(100)  # Ler primeiros 100 bytes para testar
                    logger.info("✅ Ficheiro gzip válido")
                except Exception as e:
                    raise Exception(f"Ficheiro gzip inválido: {e}")
                
                return True
                
            except requests.exceptions.RequestException as e:
                logger.warning(f"Tentativa {tentativa + 1} falhou: {e}")
                if tentativa == max_tentativas - 1:
                    raise
                logger.info("Aguardando 5 segundos antes da próxima tentativa...")
                import time
                time.sleep(5)
        
        return False
        
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
        
        if tamanho < 1000:
            raise Exception("Ficheiro XML descomprimido muito pequeno")
            
        return True
        
    except Exception as e:
        logger.error(f"❌ Erro na descompressão: {e}")
        return False

def processar_xml():
    """Processa o XML aplicando +1 minuto e 1 segundo"""
    try:
        logger.info("🔄 A processar XML...")
        
        # Parse do XML com encoding detection
        parser = etree.XMLParser(recover=True, encoding='utf-8')
        
        try:
            with open("origem.xml", "rb") as f:
                tree = etree.parse(f, parser)
        except Exception as e:
            logger.warning(f"Erro com parser UTF-8, tentando parser genérico: {e}")
            parser = etree.XMLParser(recover=True)
            with open("origem.xml", "rb") as f:
                tree = etree.parse(f, parser)
        
        root = tree.getroot()
        logger.info(f"XML carregado - Root tag: {root.tag}")
        
        # Contar programas e canais
        programas = root.findall("programme")
        canais = root.findall("channel")
        logger.info(f"Encontrados {len(canais)} canais e {len(programas)} programas")
        
        if len(programas) == 0:
            raise Exception("Nenhum programa encontrado no XML")
        
        # Contar programas processados
        programas_processados = 0
        programas_com_erro = 0
        
        # Processar cada programa
        for prog in programas:
            try:
                # Processar horário de início
                if "start" in prog.attrib:
                    start_original = prog.attrib["start"]
                    start_ajustado = ajustar_tempo(start_original)
                    prog.attrib["start"] = start_ajustado
                    
                    # Debug para primeiros 5 programas
                    if programas_processados < 5:
                        logger.info(f"Programa {programas_processados + 1}: {start_original} → {start_ajustado}")
                
                # Processar horário de fim
                if "stop" in prog.attrib:
                    stop_original = prog.attrib["stop"]
                    stop_ajustado = ajustar_tempo(stop_original)
                    prog.attrib["stop"] = stop_ajustado
                
                programas_processados += 1
                
            except Exception as e:
                programas_com_erro += 1
                logger.warning(f"Erro ao processar programa {prog.get('start', 'unknown')}: {e}")
        
        logger.info(f"✅ Processamento concluído:")
        logger.info(f"   - Programas processados: {programas_processados}")
        logger.info(f"   - Programas com erro: {programas_com_erro}")
        
        if programas_processados == 0:
            raise Exception("Nenhum programa foi processado com sucesso")
        
        # Guardar XML processado com encoding correto
        try:
            with open("compilacao.xml", "wb") as f:
                tree.write(f, encoding="utf-8", xml_declaration=True, pretty_print=True)
            
            # Verificar se o ficheiro foi criado
            tamanho_compilacao = os.path.getsize("compilacao.xml")
            logger.info(f"✅ Ficheiro compilacao.xml criado: {tamanho_compilacao:,} bytes")
            
        except Exception as e:
            logger.error(f"Erro ao guardar XML: {e}")
            # Tentar sem pretty_print
            with open("compilacao.xml", "wb") as f:
                tree.write(f, encoding="utf-8", xml_declaration=True)
            logger.info("✅ XML guardado sem formatação")
        
        return True
        
    except Exception as e:
        logger.error(f"❌ Erro no processamento XML: {e}")
        return False

def ajustar_tempo(valor_tempo):
    """Ajusta o tempo adicionando 1 minuto e 1 segundo"""
    try:
        # Remover espaços extras
        valor_tempo = valor_tempo.strip()
        
        # Formato esperado: YYYYMMDDHHMMSS +TZTZ ou YYYYMMDDHHMMSS
        if len(valor_tempo) >= 14:
            # Separar data/hora do timezone
            parte_data = valor_tempo[:14]
            parte_timezone = valor_tempo[14:].strip()
            
            # Verificar se a parte da data é numérica
            if not parte_data.isdigit():
                logger.warning(f"Parte da data não é numérica: {parte_data}")
                return valor_tempo
            
            # Converter para datetime
            dt = datetime.strptime(parte_data, "%Y%m%d%H%M%S")
            
            # Adicionar 1 minuto e 1 segundo
            dt += timedelta(minutes=1, seconds=1)
            
            # Reconstruir string
            nova_data = dt.strftime("%Y%m%d%H%M%S")
            
            # Manter timezone original se existir
            if parte_timezone:
                return f"{nova_data} {parte_timezone}"
            else:
                return nova_data
        else:
            logger.warning(f"Formato de tempo inválido (muito curto): {valor_tempo}")
            return valor_tempo
            
    except ValueError as e:
        logger.warning(f"Erro ao converter tempo '{valor_tempo}': {e}")
        return valor_tempo
    except Exception as e:
        logger.warning(f"Erro inesperado ao ajustar tempo '{valor_tempo}': {e}")
        return valor_tempo

def comprimir_xml():
    """Comprime o XML final"""
    try:
        logger.info("🔄 A comprimir ficheiro final...")
        
        # Verificar se o ficheiro XML existe
        if not os.path.exists("compilacao.xml"):
            raise Exception("Ficheiro compilacao.xml não encontrado")
        
        tamanho_original = os.path.getsize("compilacao.xml")
        logger.info(f"Tamanho original: {tamanho_original:,} bytes")
        
        with open("compilacao.xml", "rb") as f_in:
            with gzip.open("compilacao.xml.gz", "wb", compresslevel=9) as f_out:
                shutil.copyfileobj(f_in, f_out)
        
        # Verificar ficheiro comprimido
        tamanho_final = os.path.getsize("compilacao.xml.gz")
        ratio = (1 - tamanho_final/tamanho_original) * 100
        
        logger.info(f"✅ Compressão concluída:")
        logger.info(f"   - Tamanho final: {tamanho_final:,} bytes")
        logger.info(f"   - Ratio de compressão: {ratio:.1f}%")
        
        return True
        
    except Exception as e:
        logger.error(f"❌ Erro na compressão: {e}")
        return False

def verificar_ficheiros_finais():
    """Verifica se os ficheiros finais foram criados corretamente"""
    try:
        logger.info("🔄 Verificando ficheiros finais...")
        
        # Verificar compilacao.xml
        if not os.path.exists("compilacao.xml"):
            raise Exception("compilacao.xml não encontrado")
        
        xml_size = os.path.getsize("compilacao.xml")
        if xml_size < 1000:
            raise Exception("compilacao.xml muito pequeno")
        
        # Verificar compilacao.xml.gz
        if not os.path.exists("compilacao.xml.gz"):
            raise Exception("compilacao.xml.gz não encontrado")
        
        gz_size = os.path.getsize("compilacao.xml.gz")
        if gz_size < 500:
            raise Exception("compilacao.xml.gz muito pequeno")
        
        # Testar se o .gz pode ser descomprimido
        try:
            with gzip.open("compilacao.xml.gz", "rb") as f:
                test_data = f.read(1000)
                if len(test_data) < 100:
                    raise Exception("Conteúdo descomprimido muito pequeno")
        except Exception as e:
            raise Exception(f"Erro ao testar descompressão: {e}")
        
        logger.info("✅ Verificação dos ficheiros finais concluída com sucesso")
        logger.info(f"   - compilacao.xml: {xml_size:,} bytes")
        logger.info(f"   - compilacao.xml.gz: {gz_size:,} bytes")
        
        return True
        
    except Exception as e:
        logger.error(f"❌ Erro na verificação final: {e}")
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
        
        # 6. Verificar ficheiros finais
        if not verificar_ficheiros_finais():
            logger.error("❌ Falha na verificação final - processo abortado")
            return False
        
        # 7. Limpar ficheiros temporários
        limpar_ficheiros_temporarios()
        
        logger.info("🎉 Processo concluído com sucesso!")
        logger.info("📁 Ficheiros finais criados:")
        logger.info("   - compilacao.xml")
        logger.info("   - compilacao.xml.gz")
        
        return True
        
    except Exception as e:
        logger.error(f"❌ Erro geral no processamento: {e}")
        limpar_ficheiros_temporarios()
        return False

if __name__ == "__main__":
    sucesso = main()
    sys.exit(0 if sucesso else 1)
