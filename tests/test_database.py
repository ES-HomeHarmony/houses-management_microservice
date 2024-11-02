import pytest
from app.database import get_db, SessionLocal
from unittest.mock import patch, MagicMock

# Teste para verificar se a função get_db fecha a sessão corretamente
def test_get_db_session_closed():
    with patch("app.database.SessionLocal") as mock_session:
        mock_db_instance = MagicMock()
        mock_session.return_value = mock_db_instance

        db_gen = get_db()
        db = next(db_gen)  # Inicializa o gerador para simular uma chamada
        assert db is not None  # Verifica se a sessão é criada
        db_gen.close()  # Fecha o gerador para executar o bloco 'finally'

        mock_db_instance.close.assert_called_once()  # Verifica se 'close()' foi chamado na instância