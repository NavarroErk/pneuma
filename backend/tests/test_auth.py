def test_login(client):
    # admin/password already created
    assert client.post("/login", data={"username": "admin", "password": "password"}).status_code == 200
    assert client.post("/login", data={"username": "admin", "password": "wrong"}).status_code == 401
    assert client.post("/login", data={"username": "nobody", "password": "x"}).status_code == 401
    
def test_logout(client):
    assert client.post("/logout").status_code == 204
    assert client.get("/entries").status_code == 401  # token no longer works

def test_setup_only_once(client):
    # the fixture already ran setup for the initial user
    res = client.post("/setup", data={"username": "attacker", "password": "pw"})
    assert res.status_code == 409
 
def test_register(client):
    assert client.post("/register", data={"username": "bob", "password": "pw"}).status_code == 200
    assert client.post("/register", data={"username": "bob", "password": "pw"}).status_code == 409