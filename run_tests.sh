#!/bin/bash
# Script pour exécuter les tests avec rapport de couverture

echo "🔒 Running security tests for CofICab platform..."
echo "=================================================="

# Naviguer au répertoire backend
cd "$(dirname "$0")/backend"

# Vérifier que pytest est installé
if ! command -v pytest &> /dev/null; then
    echo "❌ pytest not found. Installing test dependencies..."
    pip install -r requirements.txt
fi

# Exécuter les tests avec rapport de couverture
echo ""
echo "Running tests with coverage..."
pytest --cov=app --cov-report=html --cov-report=term-missing

# Résultats
echo ""
echo "✅ Test execution complete!"
echo "📊 Coverage report: htmlcov/index.html"
echo ""
echo "To view the coverage report, open: htmlcov/index.html"
