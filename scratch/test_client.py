from fastapi.testclient import TestClient
from app.main import app
from app.middleware.authentication import CurrentUser
from app.modules.administration.domain.enums import Role
from uuid import UUID

# Mock a logged in user in request state
client = TestClient(app)

# We can bypass auth middleware by setting request.state.user in a custom middleware or just getting a token.
# Let's see if we can perform login:
response = client.post("/auth/login", data={"username": "admin@vitco.com", "password": "password"})
print("Login status:", response.status_code)
cookies = response.cookies

# Call the endpoint
res = client.get("/farmer/api/ratecharts?vlcc_id=106d1c73-ebec-4b21-b78e-0c882eaf99ab", cookies=cookies)
print("STATUS:", res.status_code)
print("RESPONSE HEADERS:", res.headers)
print("RESPONSE TEXT:")
print(res.text)
