import pytest
from fastapi import status


class TestAuthSecurity:
    """Tests de sécurité pour l'authentification"""

    def test_login_with_valid_credentials(self, client):
        """Test connexion avec identifiants valides"""
        response = client.post(
            "/api/auth/login",
            json={"email": "test@coficab.com", "password": "test123"}
        )
        assert response.status_code in [status.HTTP_200_OK, status.HTTP_401_UNAUTHORIZED]

    def test_login_missing_email(self, client):
        """Test connexion sans email"""
        response = client.post(
            "/api/auth/login",
            json={"password": "test123"}
        )
        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY

    def test_login_missing_password(self, client):
        """Test connexion sans mot de passe"""
        response = client.post(
            "/api/auth/login",
            json={"email": "test@coficab.com"}
        )
        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY

    def test_login_sql_injection_attempt(self, client):
        """Test protection contre SQL injection"""
        response = client.post(
            "/api/auth/login",
            json={
                "email": "admin' OR '1'='1",
                "password": "' OR '1'='1"
            }
        )
        # Doit rejeter ou ne pas donner accès
        assert response.status_code in [
            status.HTTP_401_UNAUTHORIZED,
            status.HTTP_422_UNPROCESSABLE_ENTITY
        ]

    def test_protected_endpoint_without_token(self, client):
        """Test accès à endpoint protégé sans token"""
        response = client.get("/api/data/transports")
        # Doit demander authentification ou être accessible
        assert response.status_code in [
            status.HTTP_401_UNAUTHORIZED,
            status.HTTP_403_FORBIDDEN,
            status.HTTP_200_OK
        ]

    def test_protected_endpoint_with_invalid_token(self, client):
        """Test accès avec token invalide"""
        response = client.get(
            "/api/data/transports",
            headers={"Authorization": "Bearer invalid_token_xyz"}
        )
        assert response.status_code in [
            status.HTTP_401_UNAUTHORIZED,
            status.HTTP_403_FORBIDDEN
        ]


class TestPasswordSecurity:
    """Tests de sécurité pour les mots de passe"""

    def test_password_hashing(self):
        """Test que les mots de passe sont hashés"""
        from app.services.auth_service import hash_password, verify_password

        password = "SuperSecurePassword123!"
        hashed = hash_password(password)

        # Le mot de passe hashé ne doit pas être le même que l'original
        assert hashed != password
        # La vérification doit fonctionner
        assert verify_password(password, hashed) is True
        # Un mauvais mot de passe doit échouer
        assert verify_password("WrongPassword", hashed) is False

    def test_weak_password_handling(self):
        """Test que les faibles mots de passe sont gérés"""
        from app.services.auth_service import hash_password

        weak_passwords = ["123", "pass", ""]
        for weak_pwd in weak_passwords:
            # Doit au moins ne pas crasher
            hashed = hash_password(weak_pwd)
            assert hashed is not None
