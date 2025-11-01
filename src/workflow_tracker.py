"""
Workflow Tracker - заглушка для отслеживания этапов
"""
import logging

logger = logging.getLogger(__name__)


class WorkflowTracker:
    """Трекер workflow - заглушка"""
    
    def __init__(self, admin_panel_url: str = "http://localhost:8000"):
        self.enabled = False
    
    def start_workflow(self, user_id: int, title: str, stages: list) -> str:
        """Начать workflow"""
        logger.debug(f"Workflow started: {title}")
        return f"wf_{user_id}"
    
    def update_stage(self, workflow_id: str, stage_id: int, status: str, metadata: dict = None):
        """Обновить этап"""
        logger.debug(f"Stage {stage_id} updated: {status}")
    
    def complete_workflow(self, workflow_id: str, output_file: str = None):
        """Завершить workflow"""
        logger.debug(f"Workflow {workflow_id} completed")
    
    def error_workflow(self, error_message: str, stage_id: int = None):
        """Ошибка в workflow"""
        logger.debug(f"Workflow error: {error_message}")
