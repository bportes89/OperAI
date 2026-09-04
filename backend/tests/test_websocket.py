import pytest
from uuid import uuid4
from unittest.mock import Mock, patch, AsyncMock

from app.websocket import (
    ConnectionManager, manager,
    notify_task_completed, notify_task_failed, notify_task_created
)
from starlette.websockets import WebSocketState


class TestConnectionManager:
    @pytest.fixture
    def ws_manager(self):
        return ConnectionManager()

    @pytest.fixture
    def mock_websocket(self):
        ws = Mock()
        ws.accept = AsyncMock()
        ws.send_json = AsyncMock()
        ws.close = AsyncMock()
        ws.client_state = WebSocketState.CONNECTED
        return ws

    @pytest.mark.asyncio
    async def test_connect_new_organization(self, ws_manager, mock_websocket):
        org_id = str(uuid4())
        user_id = str(uuid4())

        await ws_manager.connect(
            websocket=mock_websocket,
            organization_id=org_id,
            user_id=user_id,
            user_name="Test User"
        )

        mock_websocket.accept.assert_called_once()
        
        assert org_id in ws_manager._connections
        assert mock_websocket in ws_manager._connections[org_id]
        assert ws_manager._ws_to_org[mock_websocket] == org_id

    @pytest.mark.asyncio
    async def test_connect_multiple_users_same_org(self, ws_manager, mock_websocket):
        """Testa múltiplos usuários na mesma organização."""
        org_id = str(uuid4())

        # Primeiro usuário
        ws1 = Mock()
        ws1.accept = AsyncMock()
        
        await ws_manager.connect(
            websocket=ws1,
            organization_id=org_id,
            user_id=str(uuid4()),
            user_name="User 1"
        )

        # Segundo usuário (mesma org)
        ws2 = Mock()
        ws2.accept = AsyncMock()

        await ws_manager.connect(
            websocket=ws2,
            organization_id=org_id,
            user_id=str(uuid4()),
            user_name="User 2"
        )

        # Verifica se ambos estão registrados
        assert len(ws_manager._connections[org_id]) == 2
        assert ws1 in ws_manager._connections[org_id]
        assert ws2 in ws_manager._connections[org_id]

    @pytest.mark.asyncio
    async def test_disconnect(self, ws_manager, mock_websocket):
        org_id = str(uuid4())
        
        # Conecta primeiro
        await ws_manager.connect(
            websocket=mock_websocket,
            organization_id=org_id,
            user_id=str(uuid4()),
            user_name="Test User"
        )

        # Desconecta
        await ws_manager.disconnect(mock_websocket)

        assert mock_websocket not in ws_manager._connections.get(org_id, set())
        assert mock_websocket not in ws_manager._ws_to_org
        assert mock_websocket not in ws_manager._ws_to_user

    @pytest.mark.asyncio
    async def test_broadcast_to_organization(self, ws_manager, mock_websocket):
        org_id = str(uuid4())
        
        await ws_manager.connect(
            websocket=mock_websocket,
            organization_id=org_id,
            user_id=str(uuid4()),
            user_name="Test User"
        )

        mock_websocket.send_json.reset_mock()
        message = {"type": "test", "data": "Hello"}
        await ws_manager.broadcast_to_organization(org_id, message)
        mock_websocket.send_json.assert_called_once()


class TestNotificationFunctions:
    @pytest.mark.asyncio
    async def test_notify_task_completed(self):
        org_id = str(uuid4())
        task_id = str(uuid4())
        
        with patch.object(manager, 'broadcast_to_organization', new_callable=AsyncMock) as mock_send:
            await notify_task_completed(
                organization_id=org_id, task_id=task_id, result={"message": "Success"}
            )

            mock_send.assert_called_once()
            call_args = mock_send.call_args[0]
            assert call_args[0] == org_id
            
            message = call_args[1]
            assert message["type"] == "task_completed"
            assert message["task_id"] == task_id

    @pytest.mark.asyncio
    async def test_notify_task_failed(self):
        org_id = str(uuid4())
        task_id = str(uuid4())
        
        with patch.object(manager, 'broadcast_to_organization', new_callable=AsyncMock) as mock_send:
            await notify_task_failed(
                organization_id=org_id, task_id=task_id, error="API Error: Rate limit exceeded"
            )

            mock_send.assert_called_once()
            call_args = mock_send.call_args[0]
            message = call_args[1]
            
            assert message["type"] == "task_failed"
            assert message["task_id"] == task_id
            assert message["error"] == "API Error: Rate limit exceeded"

    @pytest.mark.asyncio
    async def test_notify_task_created(self):
        org_id = str(uuid4())
        
        with patch.object(manager, 'broadcast_to_organization', new_callable=AsyncMock) as mock_send:
            await notify_task_created(
                organization_id=org_id,
                task_data={"id": str(uuid4()), "task_type": "marketing.campaign", "title": "Campaign Task"},
            )

            mock_send.assert_called_once()
            call_args = mock_send.call_args[0]
            message = call_args[1]
            
            assert message["type"] == "task_created"
            assert message["data"]["title"] == "Campaign Task"
