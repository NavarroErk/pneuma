def test_login(client):
    # admin/password already created
    assert client.post("/login", data={"username": "admin", "password": "password"}).status_code == 200
    assert client.post("/login", data={"username": "admin", "password": "wrong"}).status_code == 401
    assert client.post("/login", data={"username": "nobody", "password": "x"}).status_code == 401