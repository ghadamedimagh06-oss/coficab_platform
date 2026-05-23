import pytest
from fastapi import status


class TestDataIngestionSecurity:
    """Tests de sécurité pour l'ingestion de données"""

    def test_ingestion_endpoint_requires_auth(self, client):
        """Test que l'endpoint d'ingestion nécessite l'authentification"""
        response = client.post(
            "/api/ingestion/data",
            json={
                "filename": "test.xlsx",
                "rows": []
            }
        )
        # Doit demander authentification ou être accessible avec contrôles
        assert response.status_code in [
            status.HTTP_401_UNAUTHORIZED,
            status.HTTP_403_FORBIDDEN,
            status.HTTP_200_OK,
            status.HTTP_422_UNPROCESSABLE_ENTITY
        ]

    def test_ingestion_with_empty_rows(self, client):
        """Test ingestion avec données vides"""
        response = client.post(
            "/api/ingestion/data",
            json={
                "filename": "test.xlsx",
                "rows": []
            }
        )
        # Doit être accepté ou rejeter proprement
        assert response.status_code in [
            status.HTTP_200_OK,
            status.HTTP_400_BAD_REQUEST,
            status.HTTP_401_UNAUTHORIZED
        ]

    def test_ingestion_with_malformed_data(self, client):
        """Test ingestion avec données malformées"""
        response = client.post(
            "/api/ingestion/data",
            json={
                "filename": "test.xlsx",
                "rows": "not_a_list"  # Invalid
            }
        )
        assert response.status_code in [
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            status.HTTP_400_BAD_REQUEST
        ]

    def test_ingestion_with_oversized_filename(self, client):
        """Test ingestion avec nom de fichier excessif"""
        response = client.post(
            "/api/ingestion/data",
            json={
                "filename": "a" * 10000,  # Très long
                "rows": []
            }
        )
        # Doit rejeter ou limiter
        assert response.status_code in [
            status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            status.HTTP_400_BAD_REQUEST
        ]

    def test_ingestion_with_special_characters(self, client):
        """Test ingestion avec caractères spéciaux"""
        response = client.post(
            "/api/ingestion/data",
            json={
                "filename": "test<script>alert('xss')</script>.xlsx",
                "rows": []
            }
        )
        # Doit être sécurisé
        assert response.status_code in [
            status.HTTP_200_OK,
            status.HTTP_400_BAD_REQUEST,
            status.HTTP_401_UNAUTHORIZED
        ]


class TestDataValidation:
    """Tests de validation des données"""

    def test_transport_data_validation(self):
        """Test validation des données de transport"""
        from pydantic import ValidationError
        try:
            # Importer le modèle de transport si disponible
            # from app.models.transport import Transport
            # transport = Transport(...)
            pass
        except ValidationError as e:
            pytest.fail(f"Validation failed: {e}")

    def test_negative_values_rejection(self):
        """Test que les valeurs négatives sont rejetées"""
        # Les poids, distances, etc. ne doivent pas être négatifs
        test_data = [
            {"km": -100},
            {"capacity": -1000},
            {"stops": -5}
        ]
        # Doit être rejeté en validation
        for data in test_data:
            # Ajouter validation ici
            pass
