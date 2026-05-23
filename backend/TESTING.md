# Tests de Sécurité - CofICab Platform

Suite de tests de sécurité automatisés pour valider la protection du système.

## 🔒 Couverture de sécurité

### Tests d'authentification (`test_auth.py`)
- ✅ Connexion avec identifiants valides
- ✅ Rejet des champs manquants
- ✅ Protection contre SQL injection
- ✅ Rejet des tokens invalides
- ✅ Hachage des mots de passe (bcrypt)

### Tests d'ingestion de données (`test_ingestion.py`)
- ✅ Authentification requise
- ✅ Validation des données vides
- ✅ Rejet des données malformées
- ✅ Protection contre oversized payloads
- ✅ Sanitization des caractères spéciaux

## 📊 Exécuter les tests

### Avec rapport de couverture
```bash
cd backend
pytest --cov=app --cov-report=html --cov-report=term-missing
```

### Tests spécifiques
```bash
pytest tests/test_auth.py -v
pytest tests/test_ingestion.py -v
```

### Script automatisé
```bash
bash ../run_tests.sh
```

## 📈 Rapport de couverture

Le rapport HTML est généré dans `backend/htmlcov/index.html`

Seuil minimum configuré : **30%**

## 🛡️ Standards de sécurité testés

- SQL Injection
- Cross-Site Scripting (XSS)
- Authentication & Authorization
- Input Validation
- Password Hashing
- CORS & CSRF

## 🔧 Ajouter des tests

Créer un nouveau fichier dans `backend/tests/test_*.py` :

```python
import pytest

class TestNewFeature:
    def test_something(self, client):
        response = client.get("/api/endpoint")
        assert response.status_code == 200
```

Ensuite exécuter : `pytest tests/test_new_feature.py -v`
