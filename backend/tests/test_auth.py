def test_login(client):
    # admin/password already created
    assert client.post("/login", data={"username": "admin", "password": "password"}).status_code == 200
    assert client.post("/login", data={"username": "admin", "password": "wrong"}).status_code == 401
    assert client.post("/login", data={"username": "nobody", "password": "x"}).status_code == 401
    
def test_logout(client):
    assert client.post("/logout").status_code == 204
    assert client.get("/entries").status_code == 401  # token no longer works