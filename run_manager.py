#!/usr/bin/env python3
"""
Run Manager - Gerenciador de execução para EPG Processor
Versão 1.1.0

Opções de execução:
1. Automática diária (GitHub Actions)
2. Força run com timeshift específico
3. Configuração via app Android

Uso:
python run_manager.py --auto              # Execução automática
python run_manager.py --force 60          # Força timeshift de 60s
python run_manager.py --channel RTP1 30   # Define RTP1 com 30s
python run_manager.py --android-sync      # Sincroniza com app Android
"""

import os
import sys
import json
import logging
import argparse
from datetime import datetime, timedelta
from processar import EPGProcessor

# Configuração de logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class RunManager:
    """Gerenciador de execução do EPG Processor"""
    
    def __init__(self, config_path: str = "config.json"):
        self.config_path = config_path
        self.processor = EPGProcessor(config_path)
    
    def run_automatic(self) -> bool:
        """Execução automática diária"""
        logger.info("=== EXECUÇÃO AUTOMÁTICA DIÁRIA ===")
        
        # Verifica se deve executar
        if not self._should_run_automatically():
            logger.info("Execução automática não programada para agora")
            return True
        
        # Executa processamento
        success = self.processor.process()
        
        if success:
            logger.info("Execução automática concluída com sucesso")
            self._update_last_auto_run()
        else:
            logger.error("Falha na execução automática")
        
        return success
    
    def run_with_force_timeshift(self, offset_seconds: int, duration_hours: int = 24) -> bool:
        """Execução com timeshift forçado"""
        logger.info(f"=== EXECUÇÃO COM TIMESHIFT FORÇADO: {offset_seconds}s ===")
        
        # Define offset forçado
        self.processor.set_force_timeshift(offset_seconds, duration_hours)
        
        # Executa processamento
        success = self.processor.process()
        
        if success:
            logger.info(f"Execução com timeshift {offset_seconds}s concluída")
        else:
            logger.error("Falha na execução com timeshift forçado")
        
        return success
    
    def set_channel_timeshift(self, channel_id: str, offset_seconds: int) -> bool:
        """Define timeshift específico para canal"""
        logger.info(f"=== CONFIGURAÇÃO CANAL {channel_id}: {offset_seconds}s ===")
        
        # Define offset do canal
        self.processor.set_channel_timeshift(channel_id, offset_seconds)
        
        # Executa processamento
        success = self.processor.process()
        
        if success:
            logger.info(f"Canal {channel_id} configurado com sucesso")
        else:
            logger.error(f"Falha ao configurar canal {channel_id}")
        
        return success
    
    def sync_with_android(self) -> bool:
        """Sincroniza configurações com app Android"""
        logger.info("=== SINCRONIZAÇÃO COM APP ANDROID ===")
        
        # Verifica se integração está habilitada
        if not self.processor.config['android_integration']['api_enabled']:
            logger.warning("Integração Android não está habilitada")
            return False
        
        try:
            # Carrega configurações pendentes do Android
            android_config_file = "android_config.json"
            
            if os.path.exists(android_config_file):
                with open(android_config_file, 'r', encoding='utf-8') as f:
                    android_config = json.load(f)
                
                # Aplica configurações do Android
                self._apply_android_config(android_config)
                
                # Remove arquivo temporário
                os.remove(android_config_file)
                
                logger.info("Configurações do Android aplicadas")
            else:
                logger.info("Nenhuma configuração pendente do Android")
            
            # Executa processamento
            success = self.processor.process()
            
            if success:
                # Gera arquivo de status para Android
                self._generate_android_status()
                logger.info("Sincronização com Android concluída")
            
            return success
            
        except Exception as e:
            logger.error(f"Erro na sincronização Android: {e}")
            return False
    
    def _should_run_automatically(self) -> bool:
        """Verifica se deve executar automaticamente"""
        config = self.processor.config
        
        # Verifica se execução automática está habilitada
        if not config['scheduling']['auto_run']:
            return False
        
        # Verifica horário programado
        run_time = config['scheduling']['run_time']
        current_time = datetime.now().strftime('%H:%M')
        
        # Tolerância de 30 minutos
        run_dt = datetime.strptime(run_time, '%H:%M')
        current_dt = datetime.strptime(current_time, '%H:%M')
        
        time_diff = abs((current_dt - run_dt).total_seconds())
        
        return time_diff <= 1800  # 30 minutos em segundos
    
    def _update_last_auto_run(self) -> None:
        """Atualiza timestamp da última execução automática"""
        self.processor.config['last_auto_run'] = datetime.now().isoformat()
        self.processor._save_config()
    
    def _apply_android_config(self, android_config: dict) -> None:
        """Aplica configurações recebidas do Android"""
        try:
            # Aplica timeshift por canal
            if 'channel_timeshifts' in android_config:
                for channel_id, offset in android_config['channel_timeshifts'].items():
                    self.processor.set_channel_timeshift(channel_id, offset)
                    logger.info(f"Canal {channel_id} configurado: {offset}s")
            
            # Aplica timeshift padrão
            if 'default_timeshift' in android_config:
                self.processor.config['timeshift']['default_offset_seconds'] = android_config['default_timeshift']
                logger.info(f"Timeshift padrão: {android_config['default_timeshift']}s")
            
            # Aplica outras configurações
            if 'scheduling' in android_config:
                self.processor.config['scheduling'].update(android_config['scheduling'])
                logger.info("Configurações de agendamento atualizadas")
            
            # Salva configurações
            self.processor._save_config()
            
        except Exception as e:
            logger.error(f"Erro ao aplicar configurações Android: {e}")
    
    def _generate_android_status(self) -> None:
        """Gera arquivo de status para o Android"""
        try:
            status = {
                'timestamp': datetime.now().isoformat(),
                'last_process_success': True,
                'channels_processed': self.processor.metrics['channels_processed'],
                'programmes_processed': self.processor.metrics['programmes_processed'],
                'current_config': {
                    'default_timeshift': self.processor.config['timeshift']['default_offset_seconds'],
                    'channel_timeshifts': self.processor.config['timeshift']['per_channel'],
                    'auto_run_enabled': self.processor.config['scheduling']['auto_run'],
                    'run_time': self.processor.config['scheduling']['run_time']
                },
                'available_channels': self._get_available_channels(),
                'next_scheduled_run': self._get_next_scheduled_run()
            }
            
            with open('android_status.json', 'w', encoding='utf-8') as f:
                json.dump(status, f, indent=2, ensure_ascii=False)
            
            logger.info("Status para Android gerado")
            
        except Exception as e:
            logger.error(f"Erro ao gerar status Android: {e}")
    
    def _get_available_channels(self) -> list:
        """Obtém lista de canais disponíveis"""
        # Esta função será expandida na próxima etapa
        # Por ora, retorna canais configurados
        channels = []
        
        for channel_id, offset in self.processor.config['timeshift']['per_channel'].items():
            channels.append({
                'id': channel_id,
                'name': channel_id,  # Será melhorado na próxima etapa
                'current_offset': offset
            })
        
        return channels
    
    def _get_next_scheduled_run(self) -> str:
        """Calcula próxima execução programada"""
        if not self.processor.config['scheduling']['auto_run']:
            return None
        
        run_time = self.processor.config['scheduling']['run_time']
        today = datetime.now().date()
        
        # Tenta hoje
        next_run = datetime.combine(today, datetime.strptime(run_time, '%H:%M').time())
        
        # Se já passou, agenda para amanhã
        if next_run <= datetime.now():
            next_run += timedelta(days=1)
        
        return next_run.isoformat()
    
    def get_status_report(self) -> dict:
        """Retorna relatório de status completo"""
        return {
            'system': {
                'version': self.processor.config['app_version'],
                'last_update': self.processor.config['last_update'],
                'auto_run_enabled': self.processor.config['scheduling']['auto_run']
            },
            'timeshift': {
                'default_offset': self.processor.config['timeshift']['default_offset_seconds'],
                'channels_configured': len(self.processor.config['timeshift']['per_channel']),
                'force_offset_active': self.processor.config['timeshift']['force_offset'] is not None
            },
            'android_integration': {
                'enabled': self.processor.config['android_integration']['api_enabled'],
                'last_sync': self.processor.config.get('last_android_sync', 'Never')
            },
            'next_run': self._get_next_scheduled_run()
        }
    
    def list_channels(self) -> None:
        """Lista canais configurados"""
        print("\n=== CANAIS CONFIGURADOS ===")
        print(f"Timeshift padrão: {self.processor.config['timeshift']['default_offset_seconds']}s")
        
        per_channel = self.processor.config['timeshift']['per_channel']
        if per_channel:
            print("\nCanais com timeshift específico:")
            for channel_id, offset in per_channel.items():
                print(f"  {channel_id}: {offset}s")
        else:
            print("\nNenhum canal com timeshift específico configurado")
        
        force_offset = self.processor.config['timeshift']['force_offset']
        if force_offset is not None:
            expiry = self.processor.config['timeshift']['force_offset_expiry']
            print(f"\nOffset forçado ativo: {force_offset}s até {expiry}")
        
        print()


def main():
    """Função principal com opções de execução"""
    parser = argparse.ArgumentParser(description='EPG Run Manager - Gerenciador de execução')
    parser.add_argument('--config', default='config.json', help='Arquivo de configuração')
    
    # Opções principais
    group = parser.add_mutually_exclusive_group()
    group.add_argument('--auto', action='store_true', help='Execução automática diária')
    group.add_argument('--force', type=int, metavar='SECONDS', help='Força timeshift específico')
    group.add_argument('--channel', nargs=2, metavar=('CHANNEL_ID', 'OFFSET'), 
                      help='Configura timeshift para canal específico')
    group.add_argument('--android-sync', action='store_true', help='Sincroniza com app Android')
    group.add_argument('--status', action='store_true', help='Mostra status do sistema')
    group.add_argument('--list-channels', action='store_true', help='Lista canais configurados')
    
    # Opções adicionais
    parser.add_argument('--force-duration', type=int, default=24, 
                       help='Duração do offset forçado em horas (padrão: 24)')
    parser.add_argument('--verbose', action='store_true', help='Log detalhado')
    
    args = parser.parse_args()
    
    # Configura nível de log
    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)
    
    # Cria gerenciador
    manager = RunManager(args.config)
    
    # Executa ação solicitada
    success = True
    
    if args.auto:
        # Execução automática diária
        success = manager.run_automatic()
        
    elif args.force is not None:
        # Força timeshift específico
        success = manager.run_with_force_timeshift(args.force, args.force_duration)
        
    elif args.channel:
        # Configura canal específico
        channel_id, offset = args.channel
        success = manager.set_channel_timeshift(channel_id, int(offset))
        
    elif args.android_sync:
        # Sincroniza com Android
        success = manager.sync_with_android()
        
    elif args.status:
        # Mostra status
        status = manager.get_status_report()
        print(json.dumps(status, indent=2, ensure_ascii=False))
        
    elif args.list_channels:
        # Lista canais
        manager.list_channels()
        
    else:
        # Execução padrão (compatibilidade com GitHub Actions)
        success = manager.run_automatic()
    
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
