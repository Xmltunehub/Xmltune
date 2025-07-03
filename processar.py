#!/usr/bin/env python3
"""
EPG Processor - Versão Otimizada
Sistema de processamento automático de EPG com timeshift dinâmico
"""

import os
import sys
import json
import gzip
import hashlib
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
from pathlib import Path

import requests
from lxml import etree
from dateutil import parser, tz

# Configuração de logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('epg_processor.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

class EPGProcessor:
    """Processador EPG com funcionalidades avançadas"""
    
    def __init__(self, config_path: str = "config.json"):
        self.config_path = config_path
        self.config = self._load_config()
        self.stats = {
            'channels_processed': 0,
            'programmes_processed': 0,
            'programmes_modified': 0,
            'cache_hits': 0,
            'cache_misses': 0,
            'processing_time': 0,
            'errors': []
        }
        
    def _load_config(self) -> Dict:
        """Carrega configuração do arquivo JSON"""
        try:
            with open(self.config_path, 'r', encoding='utf-8') as f:
                config = json.load(f)
                
            # Configurações padrão
            default_config = {
                "offset_seconds": 30,
                "source_url": "https://epgshare01.online/epgshare01/epg_ripper_PT1.xml.gz",
                "last_update": None,
                "app_version": "1.0.0",
                "cache_enabled": True,
                "cache_duration_hours": 24,
                "validation_enabled": True,
                "channel_offsets": {},
                "user_profiles": {},
                "output_format": "xml",
                "compression_enabled": True,
                "backup_enabled": True,
                "max_retries": 3,
                "timeout_seconds": 30,
                "timezone": "Europe/Lisbon"
            }
            
            # Merge configurações
            for key, value in default_config.items():
                if key not in config:
                    config[key] = value
                    
            return config
            
        except FileNotFoundError:
            logger.warning(f"Arquivo de configuração {self.config_path} não encontrado. Usando configuração padrão.")
            return self._create_default_config()
        except json.JSONDecodeError as e:
            logger.error(f"Erro ao carregar configuração: {e}")
            return self._create_default_config()
    
    def _create_default_config(self) -> Dict:
        """Cria configuração padrão"""
        config = {
            "offset_seconds": 30,
            "source_url": "https://epgshare01.online/epgshare01/epg_ripper_PT1.xml.gz",
            "last_update": None,
            "app_version": "1.0.0",
            "cache_enabled": True,
            "cache_duration_hours": 24,
            "validation_enabled": True,
            "channel_offsets": {},
            "user_profiles": {},
            "output_format": "xml",
            "compression_enabled": True,
            "backup_enabled": True,
            "max_retries": 3,
            "timeout_seconds": 30,
            "timezone": "Europe/Lisbon"
        }
        
        # Salva configuração padrão
        try:
            with open(self.config_path, 'w', encoding='utf-8') as f:
                json.dump(config, f, indent=2, ensure_ascii=False)
            logger.info(f"Configuração padrão criada em {self.config_path}")
        except Exception as e:
            logger.error(f"Erro ao criar configuração padrão: {e}")
            
        return config
    
    def _save_config(self):
        """Salva configuração atual"""
        try:
            with open(self.config_path, 'w', encoding='utf-8') as f:
                json.dump(self.config, f, indent=2, ensure_ascii=False)
        except Exception as e:
            logger.error(f"Erro ao salvar configuração: {e}")
    
    def _get_file_hash(self, file_path: str) -> str:
        """Calcula hash SHA256 do arquivo"""
        try:
            with open(file_path, 'rb') as f:
                return hashlib.sha256(f.read()).hexdigest()
        except Exception as e:
            logger.error(f"Erro ao calcular hash: {e}")
            return ""
    
    def _is_cache_valid(self, file_path: str) -> bool:
        """Verifica se o cache ainda é válido"""
        if not self.config.get('cache_enabled', True):
            return False
            
        cache_file = f"{file_path}.cache"
        if not os.path.exists(cache_file):
            return False
            
        try:
            cache_age = datetime.now() - datetime.fromtimestamp(os.path.getmtime(cache_file))
            max_age = timedelta(hours=self.config.get('cache_duration_hours', 24))
            return cache_age < max_age
        except Exception:
            return False
    
    def _download_epg(self, url: str) -> Optional[str]:
        """Download do arquivo EPG com retry e cache"""
        temp_file = "temp_epg.xml.gz"
        
        # Verifica cache
        if self._is_cache_valid(temp_file):
            logger.info("Usando EPG em cache")
            self.stats['cache_hits'] += 1
            return temp_file
            
        self.stats['cache_misses'] += 1
        
        for attempt in range(self.config.get('max_retries', 3)):
            try:
                logger.info(f"Tentativa {attempt + 1} de download do EPG...")
                
                response = requests.get(
                    url,
                    timeout=self.config.get('timeout_seconds', 30),
                    stream=True
                )
                response.raise_for_status()
                
                with open(temp_file, 'wb') as f:
                    for chunk in response.iter_content(chunk_size=8192):
                        f.write(chunk)
                
                # Cria arquivo de cache
                if self.config.get('cache_enabled', True):
                    cache_file = f"{temp_file}.cache"
                    Path(cache_file).touch()
                
                logger.info(f"EPG baixado com sucesso ({os.path.getsize(temp_file)} bytes)")
                return temp_file
                
            except requests.RequestException as e:
                logger.error(f"Erro no download (tentativa {attempt + 1}): {e}")
                if attempt == self.config.get('max_retries', 3) - 1:
                    self.stats['errors'].append(f"Falha no download após {self.config.get('max_retries', 3)} tentativas")
                    return None
                    
        return None
    
    def _decompress_file(self, compressed_file: str, output_file: str) -> bool:
        """Descomprime arquivo gz"""
        try:
            with gzip.open(compressed_file, 'rb') as f_in:
                with open(output_file, 'wb') as f_out:
                    f_out.write(f_in.read())
            return True
        except Exception as e:
            logger.error(f"Erro na descompressão: {e}")
            self.stats['errors'].append(f"Erro na descompressão: {e}")
            return False
    
    def _validate_xml(self, xml_file: str) -> bool:
        """Valida estrutura XML do EPG"""
        if not self.config.get('validation_enabled', True):
            return True
            
        try:
            parser_xml = etree.XMLParser(recover=True)
            tree = etree.parse(xml_file, parser_xml)
            root = tree.getroot()
            
            # Validações básicas
            if root.tag != 'tv':
                logger.error("XML inválido: elemento raiz deve ser 'tv'")
                return False
                
            channels = root.findall('channel')
            programmes = root.findall('programme')
            
            if len(channels) == 0:
                logger.error("XML inválido: nenhum canal encontrado")
                return False
                
            if len(programmes) == 0:
                logger.error("XML inválido: nenhum programa encontrado")
                return False
                
            logger.info(f"XML válido: {len(channels)} canais, {len(programmes)} programas")
            return True
            
        except Exception as e:
            logger.error(f"Erro na validação XML: {e}")
            self.stats['errors'].append(f"Erro na validação XML: {e}")
            return False
    
    def _get_channel_offset(self, channel_id: str) -> int:
        """Obtém offset específico do canal"""
        channel_offsets = self.config.get('channel_offsets', {})
        return channel_offsets.get(channel_id, self.config.get('offset_seconds', 30))
    
    def _apply_timeshift(self, time_str: str, offset_seconds: int) -> str:
        """Aplica timeshift ao timestamp"""
        try:
            # Parse do timestamp
            dt = parser.parse(time_str)
            
            # Garante timezone
            if dt.tzinfo is None:
                timezone = tz.gettz(self.config.get('timezone', 'Europe/Lisbon'))
                dt = dt.replace(tzinfo=timezone)
            
            # Aplica offset
            dt_shifted = dt + timedelta(seconds=offset_seconds)
            
            # Retorna no formato original
            return dt_shifted.strftime('%Y%m%d%H%M%S %z')
            
        except Exception as e:
            logger.error(f"Erro ao aplicar timeshift: {e}")
            return time_str
    
    def _process_programmes(self, root) -> int:
        """Processa programas com timeshift dinâmico"""
        programmes = root.findall('programme')
        modified_count = 0
        
        for programme in programmes:
            try:
                channel_id = programme.get('channel', '')
                offset = self._get_channel_offset(channel_id)
                
                # Aplica timeshift em start e stop
                start_time = programme.get('start')
                stop_time = programme.get('stop')
                
                if start_time:
                    new_start = self._apply_timeshift(start_time, offset)
                    if new_start != start_time:
                        programme.set('start', new_start)
                        modified_count += 1
                
                if stop_time:
                    new_stop = self._apply_timeshift(stop_time, offset)
                    if new_stop != stop_time:
                        programme.set('stop', new_stop)
                        modified_count += 1
                
            except Exception as e:
                logger.error(f"Erro ao processar programa: {e}")
                self.stats['errors'].append(f"Erro ao processar programa: {e}")
        
        return modified_count
    
    def _backup_file(self, file_path: str):
        """Cria backup do arquivo"""
        if not self.config.get('backup_enabled', True):
            return
            
        try:
            backup_path = f"{file_path}.backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
            if os.path.exists(file_path):
                os.rename(file_path, backup_path)
                logger.info(f"Backup criado: {backup_path}")
        except Exception as e:
            logger.error(f"Erro ao criar backup: {e}")
    
    def _compress_output(self, xml_file: str) -> Optional[str]:
        """Comprime arquivo de saída"""
        if not self.config.get('compression_enabled', True):
            return xml_file
            
        try:
            compressed_file = f"{xml_file}.gz"
            with open(xml_file, 'rb') as f_in:
                with gzip.open(compressed_file, 'wb') as f_out:
                    f_out.write(f_in.read())
            
            # Remove arquivo original
            os.remove(xml_file)
            logger.info(f"Arquivo comprimido: {compressed_file}")
            return compressed_file
            
        except Exception as e:
            logger.error(f"Erro na compressão: {e}")
            return xml_file
    
    def process_epg(self) -> bool:
        """Processa EPG completo"""
        start_time = datetime.now()
        logger.info("Iniciando processamento EPG...")
        
        try:
            # Download do EPG
            source_url = self.config.get('source_url')
            if not source_url:
                logger.error("URL fonte não configurada")
                return False
                
            compressed_file = self._download_epg(source_url)
            if not compressed_file:
                return False
            
            # Descompressão
            xml_file = "epg_original.xml"
            if not self._decompress_file(compressed_file, xml_file):
                return False
            
            # Validação
            if not self._validate_xml(xml_file):
                return False
            
            # Processamento
            parser_xml = etree.XMLParser(recover=True)
            tree = etree.parse(xml_file, parser_xml)
            root = tree.getroot()
            
            # Estatísticas
            channels = root.findall('channel')
            programmes = root.findall('programme')
            
            self.stats['channels_processed'] = len(channels)
            self.stats['programmes_processed'] = len(programmes)
            
            # Aplica timeshift
            modified_count = self._process_programmes(root)
            self.stats['programmes_modified'] = modified_count
            
            # Salva resultado
            output_file = "epg_timeshift.xml"
            self._backup_file(output_file)
            
            tree.write(
                output_file,
                encoding='utf-8',
                xml_declaration=True,
                pretty_print=True
            )
            
            # Compressão opcional
            final_file = self._compress_output(output_file)
            
            # Atualiza configuração
            self.config['last_update'] = datetime.now().isoformat()
            self._save_config()
            
            # Limpeza
            for temp_file in [compressed_file, xml_file]:
                if os.path.exists(temp_file):
                    os.remove(temp_file)
            
            # Estatísticas finais
            self.stats['processing_time'] = (datetime.now() - start_time).total_seconds()
            self._log_stats()
            
            logger.info(f"Processamento concluído com sucesso: {final_file}")
            return True
            
        except Exception as e:
            logger.error(f"Erro no processamento: {e}")
            self.stats['errors'].append(f"Erro geral: {e}")
            return False
    
    def _log_stats(self):
        """Registra estatísticas do processamento"""
        logger.info("=== ESTATÍSTICAS DO PROCESSAMENTO ===")
        logger.info(f"Canais processados: {self.stats['channels_processed']}")
        logger.info(f"Programas processados: {self.stats['programmes_processed']}")
        logger.info(f"Programas modificados: {self.stats['programmes_modified']}")
        logger.info(f"Cache hits: {self.stats['cache_hits']}")
        logger.info(f"Cache misses: {self.stats['cache_misses']}")
        logger.info(f"Tempo de processamento: {self.stats['processing_time']:.2f}s")
        
        if self.stats['errors']:
            logger.warning(f"Erros encontrados: {len(self.stats['errors'])}")
            for error in self.stats['errors']:
                logger.warning(f"  - {error}")
    
    def get_stats(self) -> Dict:
        """Retorna estatísticas do processamento"""
        return self.stats.copy()
    
    def add_channel_offset(self, channel_id: str, offset_seconds: int):
        """Adiciona offset específico para um canal"""
        if 'channel_offsets' not in self.config:
            self.config['channel_offsets'] = {}
        
        self.config['channel_offsets'][channel_id] = offset_seconds
        self._save_config()
        logger.info(f"Offset configurado para canal {channel_id}: {offset_seconds}s")
    
    def remove_channel_offset(self, channel_id: str):
        """Remove offset específico de um canal"""
        if 'channel_offsets' in self.config and channel_id in self.config['channel_offsets']:
            del self.config['channel_offsets'][channel_id]
            self._save_config()
            logger.info(f"Offset removido para canal {channel_id}")
    
    def list_channel_offsets(self) -> Dict[str, int]:
        """Lista todos os offsets de canais"""
        return self.config.get('channel_offsets', {}).copy()


def main():
    """Função principal"""
    try:
        processor = EPGProcessor()
        
        # Verifica argumentos da linha de comando
        if len(sys.argv) > 1:
            if sys.argv[1] == '--stats':
                # Mostra apenas estatísticas
                processor.process_epg()
                stats = processor.get_stats()
                print(json.dumps(stats, indent=2))
                return
            elif sys.argv[1] == '--config':
                # Mostra configuração atual
                print(json.dumps(processor.config, indent=2))
                return
        
        # Processamento normal
        success = processor.process_epg()
        
        if success:
            logger.info("EPG processado com sucesso!")
            sys.exit(0)
        else:
            logger.error("Falha no processamento do EPG")
            sys.exit(1)
            
    except KeyboardInterrupt:
        logger.info("Processamento interrompido pelo usuário")
        sys.exit(1)
    except Exception as e:
        logger.error(f"Erro inesperado: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
