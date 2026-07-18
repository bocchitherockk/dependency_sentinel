# tests/test_example.py

def test_addition():
    """Test simple de base"""
    assert 1 + 1 == 2
    print("✅ Addition fonctionne")

def test_multiplication():
    """Test de multiplication"""
    assert 2 * 3 == 6
    print("✅ Multiplication fonctionne")

def test_true():
    """Test de logique"""
    assert True is True
    print("✅ La logique fonctionne")