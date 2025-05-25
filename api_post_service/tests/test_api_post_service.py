import pytest
from fastapi.testclient import TestClient
from unittest.mock import patch, MagicMock

from api_post_service.main import app, stub

client = TestClient(app)

@pytest.fixture
def token():
    return "fake-token"


def test_create_post(mocker, token):
    create_mock = mocker.patch.object(stub, "CreatePost", autospec=True)

    mock_response = MagicMock()
    mock_response.post.id = "123"
    mock_response.post.title = "Mock Title"
    mock_response.post.description = "Mock Desc"
    mock_response.post.creator_id = "mock_user"
    create_mock.return_value = mock_response

    resp = client.post(
        "/posts",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "title": "My first post",
            "description": "Hello world!",
            "is_private": False,
            "tags": ["intro", "test"]
        }
    )
    assert resp.status_code == 200 or resp.status_code == 201, resp.text
    data = resp.json()
    assert data["id"] == "123"
    assert data["title"] == "Mock Title"
    assert data["description"] == "Mock Desc"
    assert data["creator_id"] == "mock_user"

    create_mock.assert_called_once()
    args, kwargs = create_mock.call_args
    req = args[0]
    assert req.title == "My first post"
    assert req.is_private == False
    assert list(req.tags) == ["intro", "test"]


def test_list_posts(mocker, token):
    list_mock = mocker.patch.object(stub, "ListPosts", autospec=True)

    mock_response = MagicMock()
    mock_post = MagicMock()
    mock_post.id = "1"
    mock_post.title = "T"
    mock_post.description = "D"
    mock_post.creator_id = "mock_user"
    mock_post.is_private = False
    mock_post.tags = ["tag"]
    mock_response.posts = [mock_post]
    mock_response.total = 1
    mock_response.page = 1
    mock_response.page_size = 10
    list_mock.return_value = mock_response

    resp = client.get("/posts", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data["total"] == 1
    assert len(data["posts"]) == 1
    assert data["posts"][0]["id"] == "1"
    assert data["posts"][0]["title"] == "T"


def test_get_post_not_found(mocker, token):
    import grpc
    from grpc import StatusCode

    not_found_mock = mocker.patch.object(stub, "GetPost", autospec=True)

    rpc_error = grpc.RpcError()
    rpc_error.code = lambda: StatusCode.NOT_FOUND
    rpc_error.details = lambda: "Post not found"
    not_found_mock.side_effect = rpc_error

    resp = client.get("/posts/999", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 404, resp.text
    assert resp.json()["detail"] == "Post not found"