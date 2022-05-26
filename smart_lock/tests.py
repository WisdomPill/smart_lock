from rest_framework.status import HTTP_200_OK


def test_health_check(client):
    response = client.get("/health-check/")

    assert response.status_code == HTTP_200_OK
