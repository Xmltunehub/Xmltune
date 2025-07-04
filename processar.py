#!/usr/bin/env python3
"""
EPG Processor - Sistema de processamento automático de EPG
Versão 1.1.0 - Otimizada com timeshift dinâmico e integração Android

Funcionalidades:
- Timeshift dinâmico por canal
- Execução automática diária
- Força run com timeshift específico
- Integração com app Android
- Sistema de cache inteligente
- Métricas detalhadas
"""

import os
import sys
import json
import gzip
import hashlib
import logging
import argparse
from datetime import datetime, timedelta
from typing import Dict, Optional, List, Tuple
import requests
from lxml import etree
from dateutil import parser as date_parser

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
    """Classe principal para processamento de EPG"""
    
    def __init__(self, config_path: str = "config.json"):
        """Inicializa o processador EPG"""
        self.config_path = config_path
        self.config = self._load_config()
        self.metrics = {
            'start_time': datetime.now(),
            'channels_processed': 0,
            'programmes_processed': 0,
            'errors': [],
            'cache_hits': 0,
            'cache_misses': 0
        }
        
    def _load_config(self) -> Dict:
        """Carrega configuração do arquivo JSON"""
        try:
            with open(self.config_path, 'r', encoding='utf-8') as f:
                config = json.load(f)
                
            # Verifica se é formato antigo e converte
            if 'offset_seconds' in config and 'timeshift' not in config:
                config = self._convert_old_config(config)
                
            return config
        except FileNotFoundError:
            logger.error(f"Arquivo de configuração não encontrado: {self.config_path}")
            return self._get_default_config()
        except json.JSONDecodeError as e:
            logger.error(f"Erro ao decodificar JSON: {e}")
            return self._get_default_config()
    
    def _convert_old_config(self, old_config: Dict) -> Dict:
        """Converte configuração antiga para novo formato"""
        logger.info("Convertendo configuração para novo formato...")
        
        new_config = self._get_default_config()
        
        # Migra valores antigos
        if 'offset_seconds' in old_config:
            new_config['timeshift']['default_offset_seconds'] = old_config['offset_seconds']
        if 'source_url' in old_config:
            new_config['source']['url'] = old_config['source_url']
        if 'last_update' in old_config:
            new_config['last_update'] = old_config['last_update']
        if 'app_version' in old_config:
            new_config['app_version'] = old_config['app_version']
            
        # Salva nova configuração
        self._save_config(new_config)
        return new_config
    
    def _get_default_config(self) -> Dict:
        """Retorna configuração padrão"""
        return {
            "app_version": "1.1.0",
            "last_update": datetime.now().isoformat(),
            "timeshift": {
                "default_offset_seconds": 30,
                "per_channel": {},
                "force_offset": None,
                "force_offset_expiry": None
            },
            "source": {
                "url": "https://epgshare01.online/epgshare01/epg_ripper_PT1.xml.gz",
                "backup_urls": [],
                "timeout": 300,
                "retry_attempts": 3
            },
            "processing": {
                "enable_cache": True,
                "cache_duration_hours": 24,
                "validate_xml": True,
                "generate_metrics": True,
                "compress_output": False
            },
            "output": {
                "filename": "epg_processed.xml",
                "keep_backups": 3,
                "include_metadata": True
            },
            "scheduling": {
                "auto_run": True,
                "run_time": "06:00",
                "timezone": "Europe/Lisbon"
            },
            "android_integration": {
                "api_enabled": False,
                "api_port": 8080,
                "api_key": None,
                "allow_remote_config": True,
                "sync_interval_minutes": 60
            },
            "logging": {
                "level": "INFO",
                "keep_logs_days": 30,
                "detailed_metrics": True
            },
            "profiles": {
                "default": {
                    "name": "Configuração Padrão",
                    "active": True,
                    "description": "Perfil padrão para processamento automático"
                }
            }
        }
    
    def _save_config(self, config: Dict = None) -> None:
        """Salva configuração no arquivo JSON"""
        if config is None:
            config = self.config
            
        config['last_update'] = datetime.now().isoformat()
        
        try:
            with open(self.config_path, 'w', encoding='utf-8') as f:
                json.dump(config, f, indent=2, ensure_ascii=False)
            logger.info("Configuração salva com sucesso")
        except Exception as e:
            logger.error(f"Erro ao salvar configuração: {e}")
    
    def _get_cache_key(self, url: str) -> str:
        """Gera chave de cache baseada na URL"""
        return hashlib.md5(url.encode()).hexdigest()
    
    def _is_cache_valid(self, cache_file: str) -> bool:
        """Verifica se cache é válido"""
        if not os.path.exists(cache_file):
            return False
            
        cache_age = datetime.now() - datetime.fromtimestamp(os.path.getmtime(cache_file))
        max_age = timedelta(hours=self.config['processing']['cache_duration_hours'])
        
        return cache_age < max_age
    
    def _download_epg(self, url: str) -> Optional[bytes]:
        """Baixa EPG da URL com sistema de cache"""
        cache_enabled = self.config['processing']['enable_cache']
        cache_file = f"cache_{self._get_cache_key(url)}.xml.gz"
        
        # Verifica cache
        if cache_enabled and self._is_cache_valid(cache_file):
            logger.info("Usando EPG do cache")
            self.metrics['cache_hits'] += 1
            try:
                with open(cache_file, 'rb') as f:
                    return f.read()
            except Exception as e:
                logger.warning(f"Erro ao ler cache: {e}")
        
        # Download novo
        self.metrics['cache_misses'] += 1
        logger.info(f"Baixando EPG de: {url}")
        
        session = requests.Session()
        session.headers.update({
            'User-Agent': 'EPG-Processor/1.1.0'
        })
        
        for attempt in range(self.config['source']['retry_attempts']):
            try:
                response = session.get(
                    url,
                    timeout=self.config['source']['timeout'],
                    stream=True
                )
                response.raise_for_status()
                
                content = response.content
                
                # Salva no cache
                if cache_enabled:
                    try:
                        with open(cache_file, 'wb') as f:
                            f.write(content)
                        logger.info("EPG salvo no cache")
                    except Exception as e:
                        logger.warning(f"Erro ao salvar cache: {e}")
                
                return content
                
            except requests.exceptions.RequestException as e:
                logger.warning(f"Tentativa {attempt + 1} falhou: {e}")
                if attempt == self.config['source']['retry_attempts'] - 1:
                    raise
        
        return None
    
    def _get_channel_offset(self, channel_id: str) -> int:
        """Obtém offset específico para canal"""
        # Verifica se há offset forçado ativo
        force_offset = self.config['timeshift'].get('force_offset')
        force_expiry = self.config['timeshift'].get('force_offset_expiry')
        
        if force_offset is not None and force_expiry:
            expiry_time = datetime.fromisoformat(force_expiry)
            if datetime.now() < expiry_time:
                logger.info(f"Usando offset forçado: {force_offset}s")
                return force_offset
            else:
                # Remove offset expirado
                self.config['timeshift']['force_offset'] = None
                self.config['timeshift']['force_offset_expiry'] = None
        
        # Verifica offset específico do canal
        per_channel = self.config['timeshift'].get('per_channel', {})
        if channel_id in per_channel:
            return per_channel[channel_id]
        
        # Retorna offset padrão
        return self.config['timeshift']['default_offset_seconds']
    
    def _apply_timeshift(self, time_str: str, offset_seconds: int) -> str:
        """Aplica timeshift a uma string de tempo"""
        try:
            # Parse da data/hora
            dt = date_parser.parse(time_str)
            
            # Aplica offset
            dt_shifted = dt + timedelta(seconds=offset_seconds)
            
            # Retorna no formato original
            return dt_shifted.strftime('%Y%m%d%H%M%S %z').strip()
            
        except Exception as e:
            logger.warning(f"Erro ao aplicar timeshift em '{time_str}': {e}")
            return time_str
    
    def _process_xml(self, xml_content: bytes) -> Optional[str]:
        """Processa conteúdo XML aplicando timeshift"""
        try:
            # Descomprime se necessário
            if xml_content.startswith(b'\x1f\x8b'):
                xml_content = gzip.decompress(xml_content)
            
            # Parse XML
            root = etree.fromstring(xml_content)
            
            # Processa canais
            channels = root.findall('.//channel')
            for channel in channels:
                channel_id = channel.get('id', '')
                self.metrics['channels_processed'] += 1
                
                # Log detalhado se habilitado
                if self.config['logging']['detailed_metrics']:
                    logger.debug(f"Processando canal: {channel_id}")
            
            # Processa programas
            programmes = root.findall('.//programme')
            for programme in programmes:
                channel_id = programme.get('channel', '')
                offset = self._get_channel_offset(channel_id)
                
                # Aplica timeshift nos horários
                if 'start' in programme.attrib:
                    programme.set('start', self._apply_timeshift(programme.get('start'), offset))
                
                if 'stop' in programme.attrib:
                    programme.set('stop', self._apply_timeshift(programme.get('stop'), offset))
                
                self.metrics['programmes_processed'] += 1
            
            # Adiciona metadados se habilitado
            if self.config['output']['include_metadata']:
                self._add_metadata(root)
            
            # Converte para string
            xml_str = etree.tostring(root, encoding='unicode', pretty_print=True)
            
            # Validação XML se habilitada
            if self.config['processing']['validate_xml']:
                self._validate_xml(xml_str)
            
            return xml_str
            
        except Exception as e:
            logger.error(f"Erro ao processar XML: {e}")
            self.metrics['errors'].append(str(e))
            return None
    
    def _add_metadata(self, root) -> None:
        """Adiciona metadados ao XML"""
        try:
            # Encontra ou cria elemento de metadados
            metadata = root.find('.//metadata')
            if metadata is None:
                metadata = etree.SubElement(root, 'metadata')
            
            # Adiciona informações de processamento
            process_info = etree.SubElement(metadata, 'processing')
            process_info.set('processor', 'EPG-Processor')
            process_info.set('version', self.config['app_version'])
            process_info.set('timestamp', datetime.now().isoformat())
            process_info.set('timeshift_applied', 'true')
            
        except Exception as e:
            logger.warning(f"Erro ao adicionar metadados: {e}")
    
    def _validate_xml(self, xml_content: str) -> bool:
        """Valida estrutura XML"""
        try:
            etree.fromstring(xml_content.encode())
            logger.info("XML válido")
            return True
        except etree.XMLSyntaxError as e:
            logger.error(f"XML inválido: {e}")
            self.metrics['errors'].append(f"XML inválido: {e}")
            return False
    
    def _save_output(self, xml_content: str) -> None:
        """Salva XML processado"""
        output_file = self.config['output']['filename']
        
        try:
            # Cria backup se necessário
            if os.path.exists(output_file):
                self._create_backup(output_file)
            
            # Salva arquivo
            if self.config['processing']['compress_output']:
                # Salva comprimido
                with gzip.open(f"{output_file}.gz", 'wt', encoding='utf-8') as f:
                    f.write(xml_content)
                logger.info(f"EPG salvo comprimido: {output_file}.gz")
            else:
                # Salva normal
                with open(output_file, 'w', encoding='utf-8') as f:
                    f.write(xml_content)
                logger.info(f"EPG salvo: {output_file}")
            
        except Exception as e:
            logger.error(f"Erro ao salvar arquivo: {e}")
            self.metrics['errors'].append(f"Erro ao salvar: {e}")
    
    def _create_backup(self, filename: str) -> None:
        """Cria backup do arquivo existente"""
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        backup_name = f"{filename}.backup_{timestamp}"
        
        try:
            os.rename(filename, backup_name)
            logger.info(f"Backup criado: {backup_name}")
            
            # Limpa backups antigos
            self._cleanup_old_backups()
            
        except Exception as e:
            logger.warning(f"Erro ao criar backup: {e}")
    
    def _cleanup_old_backups(self) -> None:
        """Remove backups antigos"""
        max_backups = self.config['output']['keep_backups']
        base_name = self.config['output']['filename']
        
        try:
            # Lista backups
            backups = [f for f in os.listdir('.') if f.startswith(f"{base_name}.backup_")]
            backups.sort(reverse=True)  # Mais recentes primeiro
            
            # Remove excessos
            for backup in backups[max_backups:]:
                os.remove(backup)
                logger.info(f"Backup antigo removido: {backup}")
                
        except Exception as e:
            logger.warning(f"Erro ao limpar backups: {e}")
    
    def _generate_metrics_report(self) -> None:
        """Gera relatório de métricas"""
        if not self.config['processing']['generate_metrics']:
            return
        
        end_time = datetime.now()
        duration = end_time - self.metrics['start_time']
        
        report = {
            'timestamp': end_time.isoformat(),
            'duration_seconds': duration.total_seconds(),
            'channels_processed': self.metrics['channels_processed'],
            'programmes_processed': self.metrics['programmes_processed'],
            'cache_hits': self.metrics['cache_hits'],
            'cache_misses': self.metrics['cache_misses'],
            'errors': self.metrics['errors'],
            'config_version': self.config['app_version']
        }
        
        try:
            with open('metrics_report.json', 'w', encoding='utf-8') as f:
                json.dump(report, f, indent=2, ensure_ascii=False)
            
            logger.info(f"Processamento concluído:")
            logger.info(f"  - Duração: {duration.total_seconds():.2f}s")
            logger.info(f"  - Canais: {self.metrics['channels_processed']}")
            logger.info(f"  - Programas: {self.metrics['programmes_processed']}")
            logger.info(f"  - Erros: {len(self.metrics['errors'])}")
            
        except Exception as e:
            logger.error(f"Erro ao gerar relatório: {e}")
    
    def set_force_timeshift(self, offset_seconds: int, duration_hours: int = 24) -> None:
        """Define offset forçado por tempo limitado"""
        expiry = datetime.now() + timedelta(hours=duration_hours)
        
        self.config['timeshift']['force_offset'] = offset_seconds
        self.config['timeshift']['force_offset_expiry'] = expiry.isoformat()
        
        self._save_config()
        logger.info(f"Offset forçado definido: {offset_seconds}s por {duration_hours}h")
    
    def set_channel_timeshift(self, channel_id: str, offset_seconds: int) -> None:
        """Define offset específico para canal"""
        self.config['timeshift']['per_channel'][channel_id] = offset_seconds
        self._save_config()
        logger.info(f"Offset do canal {channel_id} definido: {offset_seconds}s")
    
    def get_channel_list(self) -> List[Dict]:
        """Retorna lista de canais para app Android"""
        # Esta função será expandida na próxima etapa
        return []
    
    def process(self) -> bool:
        """Executa processamento completo"""
        logger.info("Iniciando processamento EPG...")
        
        try:
            # Download EPG
            url = self.config['source']['url']
            xml_content = self._download_epg(url)
            
            if xml_content is None:
                logger.error("Falha ao baixar EPG")
                return False
            
            # Processa XML
            processed_xml = self._process_xml(xml_content)
            
            if processed_xml is None:
                logger.error("Falha ao processar XML")
                return False
            
            # Salva resultado
            self._save_output(processed_xml)
            
            # Gera relatório
            self._generate_metrics_report()
            
            # Atualiza configuração
            self._save_config()
            
            logger.info("Processamento concluído com sucesso!")
            return True
            
        except Exception as e:
            logger.error(f"Erro no processamento: {e}")
            self.metrics['errors'].append(str(e))
            return False


def main():
    """Função principal com argumentos de linha de comando"""
    parser = argparse.ArgumentParser(description='EPG Processor - Sistema de processamento automático')
    parser.add_argument('--config', default='config.json', help='Arquivo de configuração')
    parser.add_argument('--force-offset', type=int, help='Força offset específico (segundos)')
    parser.add_argument('--force-duration', type=int, default=24, help='Duração do offset forçado (horas)')
    parser.add_argument('--set-channel', nargs=2, metavar=('CHANNEL_ID', 'OFFSET'), 
                       help='Define offset para canal específico')
    parser.add_argument('--run-once', action='store_true', help='Executa uma vez e sai')
    parser.add_argument('--verbose', action='store_true', help='Log detalhado')
    
    args = parser.parse_args()
    
    # Configura nível de log
    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)
    
    # Cria processador
    processor = EPGProcessor(args.config)
    
    # Processa argumentos
    if args.force_offset is not None:
        processor.set_force_timeshift(args.force_offset, args.force_duration)
        print(f"Offset forçado definido: {args.force_offset}s por {args.force_duration}h")
    
    if args.set_channel:
        channel_id, offset = args.set_channel
        processor.set_channel_timeshift(channel_id, int(offset))
        print(f"Offset do canal {channel_id} definido: {offset}s")
    
    # Executa processamento
    if args.run_once or args.force_offset is not None or args.set_channel:
        success = processor.process()
        sys.exit(0 if success else 1)
    else:
        # Execução normal (compatibilidade com GitHub Actions)
        success = processor.process()
        sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
