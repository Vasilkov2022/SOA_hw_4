import pytest
import grpc
from datetime import datetime
from google.protobuf import empty_pb2
from google.protobuf import timestamp_pb2

import post_pb2
import post_pb2_grpc

from post_service.post_service import PostServiceServicer

class FakeContext(grpc.ServicerContext):
    def __init__(self):
        self._abort_code = None
        self._abort_details = None

    def abort(self, code, details):
        self._abort_code = code
        self._abort_details = details
        raise grpc.RpcError(f"{code}: {details}")

    def abort_with_status(self, status):
        raise grpc.RpcError(status)


@pytest.fixture
def servicer():
    return PostServiceServicer()


def test_create_post(servicer):
    ctx = FakeContext()
    request = post_pb2.CreatePostRequest(
        user_id="user123",
        title="Test Title",
        description="Test Description",
        is_private=False,
        tags=["tag1", "tag2"]
    )
    response = servicer.CreatePost(request, ctx)
    assert response.post.id == "1"
    assert response.post.title == "Test Title"
    assert response.post.creator_id == "user123"
    assert len(response.post.tags) == 2
    assert servicer.posts["1"].title == "Test Title"


def test_get_post(servicer):
    ctx = FakeContext()
    create_req = post_pb2.CreatePostRequest(
        user_id="user123",
        title="Hello",
        description="World",
        is_private=False,
        tags=[]
    )
    create_resp = servicer.CreatePost(create_req, ctx)
    post_id = create_resp.post.id

    get_req = post_pb2.GetPostRequest(user_id="user123", post_id=post_id)
    get_resp = servicer.GetPost(get_req, ctx)
    assert get_resp.post.title == "Hello"

def test_get_post_not_found(servicer):
    ctx = FakeContext()
    get_req = post_pb2.GetPostRequest(user_id="user123", post_id="999")
    with pytest.raises(grpc.RpcError) as exc_info:
        servicer.GetPost(get_req, ctx)
    assert "NOT_FOUND" in str(exc_info.value)

def test_update_post(servicer):
    ctx = FakeContext()
    create_req = post_pb2.CreatePostRequest(
        user_id="user123", title="Old", description="Desc"
    )
    create_resp = servicer.CreatePost(create_req, ctx)
    post_id = create_resp.post.id

    update_req = post_pb2.UpdatePostRequest(
        user_id="user123",
        post_id=post_id,
        title="New Title",
        description="New Desc",
        is_private=True,
        tags=["updated"]
    )
    update_resp = servicer.UpdatePost(update_req, ctx)
    assert update_resp.post.title == "New Title"
    assert update_resp.post.is_private is True
    assert update_resp.post.tags == ["updated"]

def test_delete_post(servicer):
    ctx = FakeContext()
    create_resp = servicer.CreatePost(post_pb2.CreatePostRequest(
        user_id="u", title="T", description="D"
    ), ctx)
    post_id = create_resp.post.id

    del_req = post_pb2.DeletePostRequest(user_id="u", post_id=post_id)
    del_resp = servicer.DeletePost(del_req, ctx)
    assert isinstance(del_resp, empty_pb2.Empty)

    assert post_id not in servicer.posts

def test_list_posts(servicer):
    ctx = FakeContext()
    for i in range(5):
        servicer.CreatePost(post_pb2.CreatePostRequest(
            user_id="u", title=f"title{i}", description="", is_private=False
        ), ctx)

    list_req = post_pb2.ListPostsRequest(user_id="u", page=1, page_size=10)
    list_resp = servicer.ListPosts(list_req, ctx)
    assert list_resp.total == 5
    assert len(list_resp.posts) == 5