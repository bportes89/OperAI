"""
WebSocket manager para atualizações em tempo real.
Usado para notificar sobre mudanças em AgentTasks e outras atualizações em tempo real.
"""
import json
import logging
from typing import Dict, List, Set
from datetime import datetime, timezone

from fastapi import WebSocket, WebSocketDisconnect
from starlette.websockets import WebSocketState

from .auth import Principal

logger = logging.getLogger(__name__)


class ConnectionManager:
    """Gerencia conexões WebSocket por organização."""
    
    def __init__(self):
        # organization_id -> Set[WebSocket]
        self._connections: Dict[str, Set[WebSocket]] = {}
        # websocket -> organization_id
        self._ws_to_org: Dict[WebSocket, str] = {}
        # websocket -> user info
        self._ws_to_user: Dict[WebSocket, dict] = {}
    
    async def connect(
        self,
        websocket: WebSocket,
        organization_id: str,
        user_id: str,
        user_name: str
    ):
        """Aceita nova conexão WebSocket."""
        await websocket.accept()
        
        # Registra conexão
        if organization_id not in self._connections:
            self._connections[organization_id] = set()
        
        self._connections[organization_id].add(websocket)
        self._ws_to_org[websocket] = organization_id
        self._ws_to_user[websocket] = {
            "user_id": user_id,
            "user_name": user_name
        }
        
        logger.info(
            f"[WebSocket] New connection for org {organization_id}. "
            f"Total connections: {len(self._connections[organization_id])}"
        )
        
        # Envia mensagem de confirmação
        await self._send_personal(
            websocket,
            {
                "type": "connection_established",
                "message": "Connected to OperAI real-time updates",
                "organization_id": organization_id,
                "timestamp": datetime.now(timezone.utc).isoformat()
            }
        )
    
    async def disconnect(self, websocket: WebSocket):
        """Remove conexão WebSocket."""
        organization_id = self._ws_to_org.get(websocket)
        
        if organization_id and organization_id in self._connections:
            self._connections[organization_id].discard(websocket)
            
            # Limpa se não houver mais conexões
            if not self._connections[organization_id]:
                del self._connections[organization_id]
        
        # Limpa mapeamentos
        self._ws_to_org.pop(websocket, None)
        self._ws_to_user.pop(websocket, None)
        
        if organization_id:
            logger.info(
                f"[WebSocket] Disconnected from org {organization_id}. "
                f"Remaining: {len(self._connections.get(organization_id, []))}"
            )
    
    async def broadcast_to_organization(
        self,
        organization_id: str,
        message: dict
    ):
        """Envia mensagem para todas as conexões de uma organização."""
        if organization_id not in self._connections:
            return
        
        # Adiciona timestamp
        if "timestamp" not in message:
            message["timestamp"] = datetime.now(timezone.utc).isoformat()
        
        # Envia para todas as conexões
        disconnected = []
        for websocket in list(self._connections[organization_id]):
            try:
                if websocket.client_state == WebSocketState.CONNECTED:
                    await websocket.send_json(message)
            except Exception as e:
                logger.error(f"[WebSocket] Error sending to client: {e}")
                disconnected.append(websocket)
        
        # Remove conexões quebradas
        for ws in disconnected:
            await self.disconnect(ws)
    
    async def _send_personal(self, websocket: WebSocket, message: dict):
        """Envia mensagem para uma conexão específica."""
        try:
            if websocket.client_state == WebSocketState.CONNECTED:
                await websocket.send_json(message)
        except Exception as e:
            logger.error(f"[WebSocket] Error sending personal message: {e}")
    
    def get_stats(self) -> dict:
        """Retorna estatísticas de conexões."""
        return {
            "total_organizations": len(self._connections),
            "total_connections": sum(len(conns) for conns in self._connections.values()),
            "organizations": {
                org_id: len(conns)
                for org_id, conns in self._connections.items()
            }
        }


# Instância global do manager
manager = ConnectionManager()


# Notificações específicas de tarefas

async def notify_task_created(organization_id: str, task_data: dict):
    """Notifica criação de nova tarefa."""
    await manager.broadcast_to_organization(
        organization_id,
        {
            "type": "task_created",
            "data": task_data
        }
    )


async def notify_task_completed(organization_id: str, task_id: str, result: dict):
    """Notifica conclusão de tarefa."""
    await manager.broadcast_to_organization(
        organization_id,
        {
            "type": "task_completed",
            "task_id": task_id,
            "result": result
        }
    )


async def notify_task_failed(organization_id: str, task_id: str, error: str):
    """Notifica falha em tarefa."""
    await manager.broadcast_to_organization(
        organization_id,
        {
            "type": "task_failed",
            "task_id": task_id,
            "error": error
        }
    )


async def notify_task_queue_stats(organization_id: str, stats: dict):
    """Notifica estatísticas da fila de tarefas."""
    await manager.broadcast_to_organization(
        organization_id,
        {
            "type": "task_queue_stats",
            "stats": stats
        }
    )